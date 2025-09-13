"""Utility functions for document analysis and processing."""

import logging
from pathlib import Path
from typing import Dict, Any, List
from docx.oxml.shared import qn

logger = logging.getLogger(__name__)

class DocumentAnalyzer:
    """Utility class for document structure analysis."""
    
    @staticmethod
    def analyze_paragraph_structure(paragraph):
        """Analyze paragraph formatting and structure."""
        structure = {
            'text': paragraph.text,
            'is_bold': False,
            'is_italic': False,
            'alignment': paragraph.alignment,
            'style_name': paragraph.style.name if paragraph.style else 'Normal',
            'has_numbering': False,
            'indent_level': 0,
            'has_image': False,
            'image_data': None
        }
        
        # Check for formatting in runs and images
        for run in paragraph.runs:
            if run.bold:
                structure['is_bold'] = True
            if run.italic:
                structure['is_italic'] = True
            
            # Check for images in this run
            if run._element.xpath('.//pic:pic'):
                structure['has_image'] = True
                # Extract image data
                for img in run._element.xpath('.//a:blip'):
                    image_id = img.get(qn('r:embed'))
                    if image_id:
                        structure['image_data'] = image_id
                        break
        
        return structure
    
    @staticmethod
    def extract_images_from_document(doc) -> Dict[str, Dict[str, Any]]:
        """Extract images from document relationships."""
        images = {}
        image_count = 0
        
        if hasattr(doc.part, 'related_parts'):
            for rel_id, related_part in doc.part.related_parts.items():
                if "image" in related_part.content_type:
                    images[rel_id] = {
                        'data': related_part.blob,
                        'content_type': related_part.content_type,
                        'filename': f"image_{image_count}.{related_part.content_type.split('/')[-1]}"
                    }
                    image_count += 1
                    logger.info(f"Found image: {rel_id} ({related_part.content_type})")
        
        return images
    
    @staticmethod
    def extract_tables_from_document(doc) -> List[Dict[str, Any]]:
        """Extract tables from document."""
        tables = []
        
        for i, table in enumerate(doc.tables):
            table_data = []
            for row in table.rows:
                row_data = [cell.text for cell in row.cells]
                table_data.append(row_data)
            
            tables.append({
                'index': i,
                'data': table_data,
                'rows': len(table.rows),
                'cols': len(table.rows[0].cells) if table.rows else 0
            })
        
        return tables

class PathResolver:
    """Utility class for resolving file paths."""
    
    @staticmethod
    def resolve_file_path(file_path: str) -> Path:
        """Resolve file path by checking multiple possible locations."""
        path = Path(file_path)
        if path.exists():
            return path
        
        # Try different path variations
        possible_paths = [
            Path(file_path),
            Path.cwd() / file_path,
            Path.cwd() / "input.docx",
            Path.home() / "Desktop" / file_path,
            Path.home() / "Desktop" / "input.docx"
        ]
        
        for p in possible_paths:
            if p.exists():
                logger.info(f"Resolved file path: {p}")
                return p
        
        raise FileNotFoundError(
            f"Could not find file at any of these locations: {[str(p) for p in possible_paths]}"
        )

class TextCleaner:
    """Utility class for cleaning translation results."""
    
    PREFIXES_TO_REMOVE = [
        "Translation:",
        "Here is the translation:",
        "The translation is:",
        "Translated text:",
        "Result:",
        "Output:",
        "Answer:",
        "Response:",
    ]
    
    METADATA_KEYWORDS = [
        'used_tools=', 
        'tools_errors=', 
        'delegations=', 
        'i18n='
    ]
    
    @classmethod
    def clean_translation_result(cls, result_text: str) -> str:
        """Clean translation result to extract only the translated text."""
        text = str(result_text).strip()
        
        # Remove common prefixes that models might add
        for prefix in cls.PREFIXES_TO_REMOVE:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
                break
        
        # Remove any lines that look like metadata or system messages
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip lines that look like system metadata
            if any(keyword in line.lower() for keyword in cls.METADATA_KEYWORDS):
                continue
            if line.startswith('[Translation of item'):
                continue
            if line and not line.startswith('#'):  # Skip empty lines and comments
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
