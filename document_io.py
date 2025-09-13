"""Document I/O tools for reading and writing DOCX files."""

import logging
from typing import Dict, Any
from pathlib import Path

# Import CrewAI components properly
try:
    from crewai.tools.base_tool import BaseTool
except ImportError:
    try:
        from crewai.tools import BaseTool
    except ImportError:
        try:
            from crewai import BaseTool
        except ImportError:
            # Create a simple base class if CrewAI BaseTool is not available
            class BaseTool:
                name: str = ""
                description: str = ""
                
                def _run(self, *args, **kwargs):
                    raise NotImplementedError

from docx import Document
from utils import DocumentAnalyzer, PathResolver

logger = logging.getLogger(__name__)

class DocumentReader(BaseTool):
    """Tool for reading DOCX files and extracting structured content including images."""
    
    name: str = "Document Reader"
    description: str = "Reads DOCX files and extracts structured content including images"
    
    def _run(self, file_path: str) -> Dict[str, Any]:
        """Read and analyze document structure including images."""
        try:
            path = PathResolver.resolve_file_path(file_path)
            logger.info(f"Reading document from: {path}")
            
            doc = Document(str(path))
            
            content = {
                'paragraphs': [],
                'tables': [],
                'images': {},
                'metadata': {
                    'total_paragraphs': 0,
                    'total_tables': len(doc.tables),
                    'total_images': 0,
                    'has_footnotes': False
                }
            }
            
            # Extract images from document relationships
            content['images'] = DocumentAnalyzer.extract_images_from_document(doc)
            content['metadata']['total_images'] = len(content['images'])
            
            # Extract paragraphs with structure
            for i, paragraph in enumerate(doc.paragraphs):
                structure = DocumentAnalyzer.analyze_paragraph_structure(paragraph)
                structure['index'] = i
                
                # Store paragraph even if it's empty but contains an image
                if paragraph.text.strip() or structure['has_image']:
                    content['paragraphs'].append(structure)
            
            # Extract tables
            content['tables'] = DocumentAnalyzer.extract_tables_from_document(doc)
            content['metadata']['total_paragraphs'] = len(content['paragraphs'])
            
            logger.info(
                f"Successfully analyzed document: {len(content['paragraphs'])} paragraphs, "
                f"{len(content['tables'])} tables, {len(content['images'])} images"
            )
            return content
            
        except Exception as e:
            logger.error(f"Error reading document: {str(e)}")
            raise

class DocumentWriter(BaseTool):
    """Tool for writing translated content to DOCX with original formatting and images."""
    
    name: str = "Document Writer" 
    description: str = "Writes translated content to DOCX with original formatting and images"
    
    def _run(self, translated_content: Dict[str, Any], output_path: str, 
             original_doc_path: str = None) -> str:
        """Write translated content to DOCX file preserving images."""
        try:
            if original_doc_path and Path(original_doc_path).exists():
                doc = self._update_original_document(translated_content, original_doc_path)
            else:
                doc = self._create_new_document(translated_content)
            
            doc.save(output_path)
            logger.info(f"Document saved to: {output_path}")
            return f"Document successfully saved to {output_path}"
            
        except Exception as e:
            logger.error(f"Error writing document: {str(e)}")
            raise
    
    def _update_original_document(self, translated_content: Dict[str, Any], 
                                original_doc_path: str) -> Document:
        """Update original document with translations while preserving formatting and images."""
        doc = Document(original_doc_path)
        logger.info("Using original document as template to preserve images and formatting")
        
        # Update paragraph texts while preserving formatting
        translated_paragraphs = {
            p.get('index', i): p for i, p in enumerate(translated_content.get('paragraphs', []))
        }
        
        for i, paragraph in enumerate(doc.paragraphs):
            if i in translated_paragraphs:
                trans_para = translated_paragraphs[i]
                self._update_paragraph_text(paragraph, trans_para)
        
        return doc
    
    def _update_paragraph_text(self, paragraph, trans_para: Dict[str, Any]):
        """Update paragraph text while preserving images and formatting."""
        # Only update text if it's not an image-only paragraph
        if trans_para.get('text', '').strip() and not trans_para.get('has_image', False):
            # Clear existing text but preserve formatting
            for run in paragraph.runs:
                if not run._element.xpath('.//pic:pic'):  # Don't touch runs with images
                    run.text = ""
            
            # Add translated text to first run (or create one if none exist)
            if paragraph.runs:
                first_text_run = None
                for run in paragraph.runs:
                    if not run._element.xpath('.//pic:pic'):
                        first_text_run = run
                        break
                if first_text_run:
                    first_text_run.text = trans_para['text']
                else:
                    # Create new run with translated text
                    paragraph.add_run(trans_para['text'])
            else:
                paragraph.add_run(trans_para['text'])
        
        elif trans_para.get('text', '').strip() and trans_para.get('has_image', False):
            # For paragraphs with both text and images, add translated text
            text_updated = False
            for run in paragraph.runs:
                if not run._element.xpath('.//pic:pic') and not text_updated:
                    run.text = trans_para['text']
                    text_updated = True
                    break
            
            if not text_updated:
                # Add translated text as a new run
                paragraph.add_run(" " + trans_para['text'])
    
    def _create_new_document(self, translated_content: Dict[str, Any]) -> Document:
        """Create new document if original not available."""
        doc = Document()
        logger.info("Creating new document (images may not be preserved)")
        
        # Process paragraphs
        for para_data in translated_content.get('paragraphs', []):
            p = doc.add_paragraph()
            
            # Add text with formatting
            if para_data.get('text', '').strip():
                run = p.add_run(para_data['text'])
                if para_data.get('is_bold', False):
                    run.bold = True
                if para_data.get('is_italic', False):
                    run.italic = True
            
            # Set alignment
            if para_data.get('alignment'):
                p.alignment = para_data['alignment']
            
            # Note: Images cannot be easily added without access to original image data
            if para_data.get('has_image', False):
                logger.warning(
                    f"Image found in paragraph {para_data.get('index', 'unknown')} "
                    "but cannot be preserved in new document"
                )
        
        # Add tables to new document
        for table_data in translated_content.get('tables', []):
            if table_data.get('data'):
                table = doc.add_table(
                    rows=table_data['rows'], 
                    cols=table_data['cols']
                )
                
                for row_idx, row_data in enumerate(table_data['data']):
                    for col_idx, cell_text in enumerate(row_data):
                        if row_idx < len(table.rows) and col_idx < len(table.rows[0].cells):
                            table.rows[row_idx].cells[col_idx].text = cell_text
        
        return doc