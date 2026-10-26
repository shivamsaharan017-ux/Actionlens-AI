from pathlib import Path
import fitz


def extract_file(path: str, content_type: str) -> str:
    file_path = Path(path)
    if content_type == "application/pdf" or file_path.suffix.lower() == ".pdf":
        with fitz.open(file_path) as doc:
            text = "\n".join(page.get_text("text") for page in doc)
        if text.strip():
            return text.strip()
        try:
            import pytesseract
            from PIL import Image
            import io
            with fitz.open(file_path) as doc:
                pages = [pytesseract.image_to_string(Image.open(io.BytesIO(page.get_pixmap(dpi=180).tobytes("png")))) for page in doc]
            return "\n".join(pages).strip()
        except Exception:
            return ""
    if file_path.suffix.lower() in {".txt", ".md", ".csv"}:
        return file_path.read_text(encoding="utf-8", errors="replace").strip()
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(file_path)).strip()
    except Exception:
        return ""
