import fitz
import os

PDF_DIR = "C:/Users/50013525/Documents/sbc_phase_1/ZBC"
IMG_OUT_DIR = "C:/Users/50013525/Documents/sbc_phase_1/TestImage"

DPI =400

os.mkdir(IMG_OUT_DIR)
def pdf_to_img(pdf_path, out_dir, dpi=DPI):
    doc = fitz.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        zoom = dpi/72

        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix = mat, alpha = False)
        out_name = f"{os.path.splitext(os.path.basename(pdf_path))[0]}_p{page_num}.png"
        out_path = os.path.join(out_dir, out_name)
        pix.save(out_path)
        print(f"Saved {out_path}")

if __name__ == "__main__":
    for file in os.listdir(PDF_DIR):
        if file.lower().endswith(".pdf"):
            pdf_to_img(os.path.join(PDF_DIR, file), IMG_OUT_DIR, DPI)
