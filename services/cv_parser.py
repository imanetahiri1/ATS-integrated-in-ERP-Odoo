# -*- coding: utf-8 -*-
import base64
import io
import logging
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_content):
    """Extrait le texte d'un PDF en gérant les mises en page multi-colonnes."""
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages:

                # Tentative 1 : extraction normale
                page_text = page.extract_text()

                # Détection mise en page colonnes :
                # Si le texte normal contient des mots collés (sans espace)
                # c'est le signe que pdfplumber a mélangé les colonnes
                if page_text and _detect_column_merge(page_text):
                    _logger.info("Mise en page colonnes détectée — extraction par zones")
                    page_text = _extract_columns(page)

                if page_text:
                    text_parts.append(page_text)

        return '\n'.join(text_parts).strip()

    except ImportError:
        _logger.warning("pdfplumber non installé — fallback pdfminer")
        return _extract_pdf_fallback(file_content)
    except Exception as e:
        _logger.error("Erreur extraction PDF pdfplumber: %s", str(e))
        return ""


def _detect_column_merge(text):
    """
    Détecte si pdfplumber a mélangé des colonnes.
    Signe : mots collés sans espace de plus de 25 caractères.
    """
    import re
    long_words = re.findall(r'[A-Za-zÀ-ÿ]{25,}', text)
    return len(long_words) >= 2


def _extract_columns(page):
    """
    Extrait le texte d'une page multi-colonnes en détectant
    automatiquement la vraie séparation entre colonnes.
    """
    try:
        words = page.extract_words(
            x_tolerance=3,
            y_tolerance=3,
            keep_blank_chars=False,
        )

        if not words:
            return page.extract_text() or ""

        # Trouver la vraie séparation des colonnes
        # en cherchant la zone vide (gap) entre clusters de mots sur l'axe X
        x_positions = sorted(set(round(w['x0'] / 10) * 10 for w in words))
        
        # Trouver le plus grand gap entre positions X
        page_width = page.width
        best_split = page_width / 2  # valeur par défaut
        max_gap = 0
        
        for i in range(1, len(x_positions)):
            gap = x_positions[i] - x_positions[i-1]
            # Le gap doit être dans la zone centrale (20% à 80% de la page)
            position = x_positions[i-1]
            if gap > max_gap and page_width * 0.2 < position < page_width * 0.8:
                max_gap = gap
                best_split = x_positions[i-1] + gap / 2

        _logger.info("Séparation colonnes détectée à x=%.0f (page width=%.0f)", 
                     best_split, page_width)

        # Séparer les mots
        left_words = [w for w in words if w['x0'] < best_split]
        right_words = [w for w in words if w['x0'] >= best_split]

        def words_to_text(word_list):
            if not word_list:
                return ""
            lines = []
            current_line = []
            current_y = None

            for word in sorted(word_list, key=lambda w: (round(w['top'] / 4) * 4, w['x0'])):
                word_y = round(word['top'] / 4) * 4
                if current_y is None:
                    current_y = word_y
                if abs(word_y - current_y) <= 4:
                    current_line.append(word['text'])
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word['text']]
                    current_y = word_y

            if current_line:
                lines.append(' '.join(current_line))

            return '\n'.join(lines)

        left_text = words_to_text(left_words)
        right_text = words_to_text(right_words)

        result = ""
        if left_text:
            result += left_text
        if right_text:
            result += "\n\n" + right_text

        return result.strip()

    except Exception as e:
        _logger.error("Erreur extraction colonnes: %s", str(e))
        return page.extract_text() or ""
    
def _extract_pdf_fallback(file_content):
    """Fallback basique si pdfminer absent."""
    try:
        import re
        text = file_content.decode('latin-1', errors='ignore')
        strings = re.findall(r'[A-Za-zÀ-ÿ0-9\s\.\,\;\:\!\?\@\-\_\+]{4,}', text)
        return ' '.join(strings[:500])
    except Exception as e:
        _logger.error("Erreur fallback PDF: %s", str(e))
        return ""


def extract_text_from_docx(file_content):
    """Extrait le texte d'un fichier DOCX."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(file_content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(cell.text.strip())
        return '\n'.join(paragraphs)
    except ImportError:
        _logger.warning("python-docx non installé")
        return ""
    except Exception as e:
        _logger.error("Erreur extraction DOCX: %s", str(e))
        return ""


def extract_text_from_image(file_content):
    """OCR sur une image (JPG, PNG, TIFF...) via Tesseract."""
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(file_content))
        # OCR en français + anglais + arabe
        text = pytesseract.image_to_string(image, lang='fra+eng+ara')
        return text.strip()
    except ImportError:
        _logger.warning("pytesseract ou Pillow non installé — OCR image impossible")
        return ""
    except Exception as e:
        _logger.error("Erreur OCR image: %s", str(e))
        return ""


def extract_text_from_scanned_pdf(file_content):
    """OCR sur un PDF scanné : conversion page par page en image puis Tesseract."""
    try:
        from pdf2image import convert_from_bytes
        import pytesseract

        pages = convert_from_bytes(
            file_content,
            dpi=300,
            poppler_path=r"C:\Program Files\poppler-25.12.0\Library\bin"
        )

        texts = []
        for i, page in enumerate(pages):
            page_text = pytesseract.image_to_string(page, lang='fra+eng')
            if page_text.strip():
                texts.append(page_text.strip())
            _logger.info("OCR page %d/%d terminée", i + 1, len(pages))

        return '\n\n'.join(texts)

    except Exception as e:
        _logger.error("Erreur OCR PDF scanné: %s", str(e))
        return f"__OCR_ERROR__:{str(e)}"

def _is_pdf_text_empty(text):
    """Retourne True si le texte extrait d'un PDF est trop court pour être utile."""
    if not text:
        return True
    # Moins de 50 caractères utiles = probablement un PDF scanné
    clean = text.replace('\n', '').replace(' ', '').strip()
    return len(clean) < 50


def extract_text_from_cv(file_b64, filename):
    """
    Fonction principale.
    Retourne un tuple (text, error_message).
    - text  : texte extrait (str) ou "" si échec
    - error : message d'erreur ou None
    """
    if not file_b64 or not filename:
        return "", "Fichier ou nom de fichier manquant."

    try:
        file_content = base64.b64decode(file_b64)
        fname = filename.lower().strip()
        errors = None

        if fname.endswith('.pdf'):
            text = extract_text_from_pdf(file_content)
            # Si le PDF est scanné (texte vide), fallback OCR
            if _is_pdf_text_empty(text):
                _logger.info("PDF semble scanné, lancement OCR...")
                text = extract_text_from_scanned_pdf(file_content)
                if isinstance(text, str) and text.startswith("__OCR_ERROR__:"):
                    return "", text.replace("__OCR_ERROR__:", "")
                if not text:
                    errors = "OCR exécuté mais aucun texte exploitable n'a été extrait du PDF."   

        elif fname.endswith('.docx'):
            text = extract_text_from_docx(file_content)

        elif fname.endswith('.doc'):
            # .doc ancien format — décodage basique
            text = file_content.decode('latin-1', errors='ignore')

        elif fname.endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
            text = extract_text_from_image(file_content)
            if not text:
                errors = "OCR image échoué. Vérifiez que pytesseract et Tesseract sont installés."

        else:
            return "", f"Format non supporté : {filename}. Utilisez PDF, DOCX ou une image."

        if not text or len(text.strip()) < 10:
            return "", errors or "Texte trop court ou illisible. Vérifiez la qualité du fichier."

        return text.strip(), errors

    except Exception as e:
        _logger.error("Erreur générale extraction CV [%s]: %s", filename, str(e))
        return "", f"Erreur inattendue : {str(e)}"