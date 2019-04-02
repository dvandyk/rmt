#!/usr/bin/python
# vim: set sw=4 sts=4 et tw=120 :

import argparse
import logging as log
import os
import shutil
import subprocess
import sys
import uuid
import zipfile

from syncrm import *

def syncrm_cli():
    parser = argparse.ArgumentParser(description="Command line interface to interact with your reMarkable tablet's cloud storage.")
    subparsers = parser.add_subparsers(title = 'commands')

    ## begin of commands

    # fetch
    parser_checkout = subparsers.add_parser('checkout',
        description = 'Command line program to checkout the cloud storage data',
        help = 'checkout the current cloud storage data'
    )
    parser_checkout.set_defaults(cmd = checkout)

    # fetch
    parser_fetch = subparsers.add_parser('fetch',
        description = 'Command line program to fetch the current cloud storage data',
        help = 'fetch the current cloud storage data'
    )
    parser_fetch.set_defaults(cmd = fetch)

    # init
    parser_init = subparsers.add_parser('init',
        description = 'Command line program to initialize the local repository',
        help = 'initialize the local repository'
    )
    parser_init.add_argument('DIRECTORY',
        type = str,
        help = 'directory to initialize as a syncrm repository',
        nargs = '?',
        default = os.getcwd()
    )
    parser_init.add_argument('ONE_TIME_CODE',
        metavar = 'ONE-TIME-CODE',
        type = str,
        help = 'one-time code obtained from https://my.remarkable.com'
    )
    parser_init.set_defaults(cmd = init)

    # status
    parser_status = subparsers.add_parser('status',
        description = 'Command line program to inspect the status of the local repository',
        help = 'print the status of the local repository'
    )
    parser_status.set_defaults(cmd = status)

    ## end of commands

    # add verbosity arg to all commands
    for p in parser, parser_checkout, parser_fetch, parser_init, parser_status:
        p.add_argument('-v', '--verbose',
            help = 'increase output verbosity',
            action = 'store_true'
        )

    args = parser.parse_args()

    if args.verbose:
        log.basicConfig(level=log.DEBUG)

    try:
        args.cmd(args)
    except AttributeError:
        parser.print_help()


def checkout(args):
    try:
        lock_file, repo_dir = _lock_repo_dir()
        with lock_file:
            repo = Repository(repo_dir)
            repo.read_index()

            for item_id, item_full_name in _modified(repo_dir, repo):
                log.debug('checking out {} -> {}'.format(item_id, item_full_name))
                with zipfile.ZipFile(repo_dir + '/.syncrm/blobs/' + item_id) as item_zip:
                    item_files = []
                    item_haslines = True
                    item_haspdf = False

                    item_pdf = '{}.pdf'.format(item_id)
                    if item_pdf in item_zip.namelist():
                        item_files.append(item_pdf)
                        item_haspdf = True

                    item_lines = '{}.lines'.format(item_id)
                    if not item_lines in item_zip.namelist():
                        item_haslines = False

                    if not item_haslines and not item_haspdf:
                        log.debug('skipping item {}, since it has neither a .pdf nor a .lines file'.format(item_id))
                        continue

                    # extract
                    item_tmpdir = '/tmp/syncrm/' + item_id + '/'
                    if os.path.exists(item_tmpdir):
                        shutil.rmtree(item_tmpdir)

                    os.makedirs(item_tmpdir)
                    item_zip.extractall(path=item_tmpdir)

                    if item_haslines:
                        # create .svg page files from .lines file
                        log.debug('creating .svg file from .lines file')
                        item_linesfile = LinesFile(item_tmpdir + item_lines)
                        item_linespages = item_linesfile.to_svg(item_tmpdir + item_lines)

                        # convert all .svg page files to a single .pdf file
                        call = [
                            'rsvg-convert',
                            '-a',
                            '-f', 'pdf'
                        ]
                        call.extend(item_linespages)
                        call.extend([
                            '-o', item_tmpdir + item_lines + '.pdf'
                        ])
                        log.debug(str(call))
                        subprocess.call(call)

                    os.makedirs(os.path.dirname(repo_dir + '/' + item_full_name), exist_ok = True)

                    if item_haspdf and item_haslines:
                        log.debug('combining original .pdf file and .annotated.pdf file')
                        subprocess.call([
                            'pdftk',
                            item_tmpdir + item_pdf,
                            'multistamp',
                            item_tmpdir + item_lines + '.pdf',
                            'output',
                            item_tmpdir + item_id + '.annotated.pdf'
                        ])
                        shutil.move(
                            item_tmpdir + '/' + item_id + '.annotated.pdf',
                            repo_dir + '/' + item_full_name + '.pdf'
                        )
                    elif item_haslines: # lines only
                        shutil.move(
                            item_tmpdir + '/' + item_id + '.lines.pdf',
                            repo_dir + '/' + item_full_name + '.pdf'
                        )
                    else: # pdf only
                        shutil.move(
                            item_tmpdir + '/' + item_id + '.pdf',
                            repo_dir + '/' + item_full_name + '.pdf'
                        )

    except Exception as e:
        log.error(e, exc_info=args.verbose)


def fetch(args):
    try:
        lock_file, repo_dir = _lock_repo_dir()
        with lock_file:
            print('fetching index ...')
            repo = Repository(repo_dir)
            api = API(repo.client_token)
            index = api.list_items(with_blob = True)
            repo.write_index(index)
            for item_id, item in repo:
                blob_path = repo_dir + '/.syncrm/blobs/' + item_id
                if os.path.exists(blob_path):
                    local_mtime = os.path.getmtime(blob_path)
                    if (local_mtime >= item.mtime):
                        print('skipping {} (-> {})'.format(item_id, item.full_name()))
                        continue

                print('fetching {} (-> {})'.format(item_id, item.full_name()))
                blob = api.download(item_id, item.blob_url)
                with open(blob_path, 'wb') as blob_file:
                    blob_file.write(blob)

    except Exception as e:
        log.error(e, exc_info=args.verbose)


def init(args):
    syncrm_dir = args.DIRECTORY + '/.syncrm'

    if os.path.exists(syncrm_dir):
        log.error('Directory {} exists; remove and run syncrm init again'.format(syncrm_dir))
        sys.exit(-1)

    os.makedirs(syncrm_dir)

    client_id = str(uuid.uuid4())

    api = API()
    api.register(args.ONE_TIME_CODE, client_id)

    with open(syncrm_dir + '/client_id', 'w') as client_id_file:
        client_id_file.write(client_id)

    with open(syncrm_dir + '/client_token', 'w') as client_token_file:
        client_token_file.write(api.client_token)

    os.makedirs(syncrm_dir + '/blobs')


def status(args):
    try:
        lock_file, repo_dir = _lock_repo_dir()
        with lock_file:
            repo = Repository(repo_dir)
            repo.read_index()

            print('The following files have either been modified or are missing:')
            print()
            for item_id, item_full_name in _modified(repo_dir, repo):
                print('    ' + item_full_name)

    except Exception as e:
        log.error(e, exc_info=args.verbose)

def move(args):
    try:
        if not len(args) == 2:
            raise RuntimeError('Expected two file names')

        src_path = os.path.realpath(args[1])
        dst_path = os.path.realpath(args[2])

        if dst_path == src_path:
            return

        lock_file, repo_dir = _lock_repo_dir()
        with lock_file:
            repo = Repository(repo_dir)
            repo.read_index()

            src_dir = os.path.dirname(src_path)
            dst_dir = os.path.dirname(dst_path)

            # move within the same folder? -> rename
            if dst_dir == src_dir:
                api = API(repo.client_token)
                src_uuid = repo.find_uuid(src_path)


    except Exception as e:
        log.error(e, exc_info=args.verbose)

def _modified(repo_dir, repo):
    modified = []

    for item_id, item in repo:
        item_full_name = item.full_name()
        item_file_name = repo_dir + '/' + item_full_name
        if not os.path.exists(item_file_name):
            modified.append((item_id, item_full_name))
            continue

        if os.path.getmtime(item_file_name) < item.mtime:
            modified.append((item_id, item_full_name))
            continue

    return modified

def _lock_repo_dir():
    repo_dir = _find_repo_dir()
    return (filelock.FileLock(_find_repo_dir() + '/.syncrm/lock'), repo_dir)


def _find_repo_dir():
    # TODO: traverse current working directory and its parents until we find the top level directory
    return os.getcwd()
