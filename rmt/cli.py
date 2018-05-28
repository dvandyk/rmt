#!/usr/bin/python
# vim: set sw=4 sts=4 et tw=120 :

import argparse
import logging as log
import os
import sys
import uuid
import zipfile
import shutil

from rmt import *

def rmt_cli():
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
        help = 'directory to initialize as an rmt repository',
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
    for p in parser_checkout, parser_fetch, parser_init, parser_status:
        p.add_argument("-v", "--verbose",
        help="increase output verbosity",
        action="store_true")

    args = parser.parse_args()
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
                with zipfile.ZipFile(repo_dir + '/.rmt/blobs/' + item_id) as item_zip:
                    item_pdf = '{}.pdf'.format(item_id)
                    if not item_pdf in item_zip.namelist():
                        continue

                    item_zip.extract(item_pdf, '/tmp/')
                    os.makedirs(os.path.dirname(repo_dir + '/' + item_full_name), exist_ok = True)
                    shutil.move('/tmp/' + item_pdf, repo_dir + '/' + item_full_name + '.pdf')

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
                blob_path = repo_dir + '/.rmt/blobs/' + item_id
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
    rmt_dir = args.DIRECTORY + '/.rmt'

    if os.path.exists(rmt_dir):
        log.error('Directory {} exists; remove and run rmt init again'.format(rmt_dir))
        sys.exit(-1)

    os.makedirs(rmt_dir)

    client_id = str(uuid.uuid4())

    api = API()
    api.register(args.ONE_TIME_CODE, client_id)

    with open(rmt_dir + '/client_id', 'w') as client_id_file:
        client_id_file.write(client_id)

    with open(rmt_dir + '/client_token', 'w') as client_token_file:
        client_token_file.write(api.client_token)

    os.makedirs(rmt_dir + '/blobs')


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
    return (filelock.FileLock(_find_repo_dir() + '/.rmt/lock'), repo_dir)


def _find_repo_dir():
    # TODO: traverse current working directory and its parents until we find the top level directory
    return os.getcwd()
