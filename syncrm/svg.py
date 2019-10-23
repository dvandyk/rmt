# Taken from https://github.com/deeplook/svglib/blob/master/scripts/svg2pdf

from datetime import datetime
from os.path import basename, dirname, exists, splitext

from reportlab.graphics import renderPDF
from svglib import svglib


def svg2pdf(path, outputPat=None):
    "Convert an SVG file to a PDF one."

    # derive output filename from output pattern
    file_info = {
        'dirname': dirname(path) or '.',
        'basename': basename(path),
        'base': basename(splitext(path)[0]),
        'ext': splitext(path)[1],
        'now': datetime.now(),
        'format': 'pdf'
    }
    out_pattern = outputPat or '%(dirname)s/%(base)s.%(format)s'
    # allow classic %%(name)s notation
    out_path = out_pattern % file_info
    # allow also newer {name} notation
    out_path = out_path.format(**file_info)

    # generate a drawing from the SVG file
    try:
        drawing = svglib.svg2rlg(path)
    except:
        print('Rendering failed.')
        raise

    # save converted file
    if drawing:
        renderPDF.drawToFile(drawing, out_path, showBoundary=0)
