"""
File handling utilities for the SkillsTown CV Analyzer application.
"""

import os
import logging
import PyPDF2
import docx

logger = logging.getLogger(__name__)

class FileHandler:
    """
    A class to handle file uploads and text extraction from different file formats.
    """
    
    def __init__(self, upload_folder, allowed_extensions):
        """
        Initialize the file handler.
        
        Args:
            upload_folder (str): Path to the folder where uploads will be stored.
            allowed_extensions (set): Set of allowed file extensions.
        """
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        
        # Create upload folder if it doesn't exist
        os.makedirs(self.upload_folder, exist_ok=True)
    
    def is_allowed_file(self, filename):
        """
        Check if a file has an allowed extension.
        
        Args:
            filename (str): Name of the file to check.
            
        Returns:
            bool: True if the file has an allowed extension, False otherwise.
        """
        _, file_ext = os.path.splitext(filename)
        return file_ext.lower() in self.allowed_extensions
    
    def extract_text(self, filepath):
        """
        Extract text from a file based on its extension.
        
        Args:
            filepath (str): Path to the file.
            
        Returns:
            str: Extracted text from the file.
        """
        _, file_ext = os.path.splitext(filepath)
        file_ext = file_ext.lower()
        
        # Map file extensions to extraction functions
        extractors = {
            '.pdf': self._extract_from_pdf,
            '.docx': self._extract_from_docx,
            '.txt': self._extract_from_txt
        }
        
        # Call the appropriate extraction function
        if file_ext in extractors:
            return extractors[file_ext](filepath)
        else:
            logger.warning(f"No extractor available for {file_ext} files")
            return ""
    
    def _extract_from_pdf(self, filepath):
        """
        Extract text from a PDF file.
        
        Args:
            filepath (str): Path to the PDF file.
            
        Returns:
            str: Extracted text from the PDF.
        """
        try:
            pdf_reader = PyPDF2.PdfReader(filepath)
            text = ""
            
            # Extract text from each page
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text() + "\n"
            
            logger.info(f"Extracted text from PDF: {filepath}")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF {filepath}: {e}")
            return ""
    
    def _extract_from_docx(self, filepath):
        """
        Extract text from a DOCX file.
        
        Args:
            filepath (str): Path to the DOCX file.
            
        Returns:
            str: Extracted text from the DOCX.
        """
        try:
            doc = docx.Document(filepath)
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
            
            logger.info(f"Extracted text from DOCX: {filepath}")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from DOCX {filepath}: {e}")
            return ""
    
    def _extract_from_txt(self, filepath):
        """
        Extract text from a TXT file.
        
        Args:
            filepath (str): Path to the TXT file.
            
        Returns:
            str: Extracted text from the TXT.
        """
        try:
            with open(filepath, 'r', errors='ignore') as file:
                text = file.read()
            
            logger.info(f"Extracted text from TXT: {filepath}")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from TXT {filepath}: {e}")
            return ""