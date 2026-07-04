import fitz  # PyMuPDF
import sys

def extract_pdf_text(input_path, output_path):
    try:
        # L'utilisation de 'with' gère automatiquement la fermeture du fichier
        with fitz.open(input_path) as pdf:
            pages_text = []
            for page in pdf:
                pages_text.append(page.get_text())
            page_count = len(pdf)
            
    except Exception as e:
        print(f"Erreur lors de la lecture du PDF : {e}")
        return False

    full_text = "\n\n".join(pages_text)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"Texte extrait avec succès → {output_path} ({page_count} pages)")
        return True
    except Exception as e:
        print(f"Erreur lors de l'écriture du fichier texte : {e}")
        return False

if __name__ == "__main__":
    input_pdf = sys.argv[1] if len(sys.argv) > 1 else "report.pdf"
    output_txt = sys.argv[2] if len(sys.argv) > 2 else "report.txt"
    
    success = extract_pdf_text(input_pdf, output_txt)
    if not success:
        sys.exit(1)