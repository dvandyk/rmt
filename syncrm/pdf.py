# Taken from http://www.blog.pythonlibrary.org/2018/04/11/splitting-and-merging-pdfs-with-python/


from PyPDF2 import PdfFileWriter, PdfFileReader


def merge_pdf(output_path, input_paths):
    pdf_writer = PdfFileWriter()

    for path in input_paths:
        pdf_reader = PdfFileReader(path)
        for page in range(pdf_reader.getNumPages()):
            pdf_writer.addPage(pdf_reader.getPage(page))

    with open(output_path, 'wb') as fh:
        pdf_writer.write(fh)
