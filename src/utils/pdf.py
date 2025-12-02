"""PDF text extraction utilities."""
import logging
from pathlib import Path
from typing import Optional
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Extracted text
    """
    if PyPDF2 is None:
        logger.warning("PyPDF2 not available, returning empty string")
        return ""
    
    try:
        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
        return ""


def load_text_from_file(file_path: str) -> str:
    """
    Load text from a file (supports .txt, .pdf, or any text file).
    
    Args:
        file_path: Path to file
    
    Returns:
        File contents as string
    """
    path = Path(file_path)
    
    if path.suffix.lower() == '.pdf':
        return extract_text_from_pdf(str(path))
    else:
        # Assume text file
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return ""

