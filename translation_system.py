"""Main translation system orchestrator."""

import logging
from typing import Dict, Any

from document_io import DocumentReader, DocumentWriter
from translation_engine import TranslationEngine, BatchProcessor
from config import Config

logger = logging.getLogger(__name__)

class TranslationSystem:
    """Main translation system that orchestrates the entire translation workflow."""
    
    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            config_manager = Config()
            config = config_manager.config
        else:
            config = config
            
        self.config = config
        self.document_reader = DocumentReader()
        self.document_writer = DocumentWriter()
        self.translation_engine = TranslationEngine(config)
        self.batch_processor = BatchProcessor(self.translation_engine)
    
    def run_translation(self) -> Dict[str, Any]:
        """Run the complete translation workflow."""
        try:
            logger.info(f"Starting translation to {self.config['target_language']}")
            
            # Step 1: Read document
            doc_content = self._read_document()
            
            # Step 2: Process paragraphs
            translated_paragraphs = self._translate_paragraphs(doc_content['paragraphs'])
            
            # Step 3: Process tables (if any)
            translated_tables = self._translate_tables(doc_content['tables'])
            
            # Step 4: Create final content structure
            translated_content = self._create_translated_content(
                translated_paragraphs, translated_tables, doc_content
            )
            
            # Step 5: Write the document
            self._write_document(translated_content)
            
            # Step 6: Generate summary
            result = self._create_result_summary(
                translated_paragraphs, translated_tables, doc_content
            )
            
            logger.info("Translation completed successfully!")
            return result
            
        except Exception as e:
            logger.error(f"Translation workflow failed: {str(e)}")
            raise
    
    def _read_document(self) -> Dict[str, Any]:
        """Read and analyze the input document."""
        logger.info("Reading document...")
        doc_content = self.document_reader._run(self.config['input_doc'])
        
        # Log image information
        if doc_content['images']:
            logger.info(f"Found {len(doc_content['images'])} images in document")
            for img_id, img_info in doc_content['images'].items():
                logger.info(f"  - Image {img_id}: {img_info['content_type']}")
        
        return doc_content
    
    def _translate_paragraphs(self, paragraphs: list) -> list:
        """Translate document paragraphs."""
        logger.info("Starting batch translation...")
        return self.batch_processor.process_paragraphs(paragraphs)
    
    def _translate_tables(self, tables: list) -> list:
        """Translate document tables (currently preserves original tables)."""
        # For now, keep tables as-is or implement table translation
        translated_tables = []
        for table_index, table in enumerate(tables):
            if table.get('data'):
                logger.info(f"Processing table {table_index + 1}")
                # TODO: Implement table translation if needed
                translated_tables.append(table)
        return translated_tables
    
    def _create_translated_content(self, translated_paragraphs: list, 
                                 translated_tables: list, doc_content: dict) -> Dict[str, Any]:
        """Create the final translated content structure."""
        return {
            'paragraphs': translated_paragraphs,
            'tables': translated_tables,
            'images': doc_content['images'],  # Preserve image data
            'metadata': doc_content['metadata']
        }
    
    def _write_document(self, translated_content: Dict[str, Any]):
        """Write the translated document."""
        logger.info("Writing translated document...")
        self.document_writer._run(
            translated_content, 
            self.config['output_doc'], 
            original_doc_path=self.config['input_doc']
        )
    
    def _create_result_summary(self, translated_paragraphs: list, 
                             translated_tables: list, doc_content: dict) -> Dict[str, Any]:
        """Create a summary of the translation results."""
        return {
            'status': 'completed',
            'output_file': self.config['output_doc'],
            'paragraphs_translated': len(translated_paragraphs),
            'tables_translated': len(translated_tables),
            'images_preserved': len(doc_content['images']),
            'total_paragraphs': len(doc_content['paragraphs']),
            'target_language': self.config['target_language']
        }