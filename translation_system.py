"""Main translation system orchestrator."""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

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
            
            # Step 2: Document analysis — build translation brief (runs once)
            self._analyse_document(doc_content['paragraphs'])

            # Step 3: Process paragraphs
            translated_paragraphs = self._translate_paragraphs(doc_content['paragraphs'])
            
            # Step 4: Process tables (if any)
            translated_tables = self._translate_tables(doc_content['tables'])

            # Step 5: Create final content structure
            translated_content = self._create_translated_content(
                translated_paragraphs, translated_tables, doc_content
            )
            
            # Step 6: Write the document
            self._write_document(translated_content)

            # Step 7: Optionally evaluate translation quality
            evaluation_metrics = self._evaluate_if_enabled(
                doc_content['paragraphs'], translated_paragraphs
            )

            # Step 7: Generate summary
            result = self._create_result_summary(
                translated_paragraphs, translated_tables, doc_content
            )
            result['evaluation'] = evaluation_metrics

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
    
    def _analyse_document(self, paragraphs: list) -> None:
        """Run Document Analyzer agent once to build a translation brief."""
        logger.info("Running document analysis...")
        self.translation_engine.analyze_document(paragraphs)

    def _translate_paragraphs(self, paragraphs: list) -> list:
        """Translate document paragraphs."""
        logger.info("Starting batch translation...")
        return self.batch_processor.process_paragraphs(paragraphs)
    
    def _translate_tables(self, tables: list) -> list:
        """Translate document tables cell by cell."""
        translated_tables = []
        batch_size = self.config.get('batch_size', 3)

        for table_index, table in enumerate(tables):
            if not table.get('data'):
                translated_tables.append(table)
                continue

            logger.info(f"Translating table {table_index + 1} ({table['rows']}x{table['cols']})")

            # Flatten non-empty cells with their positions
            cells_to_translate = []
            positions = []
            for row_idx, row in enumerate(table['data']):
                for col_idx, cell_text in enumerate(row):
                    if cell_text.strip():
                        cells_to_translate.append(cell_text)
                        positions.append((row_idx, col_idx))

            # Translate in batches
            translated_cells = []
            for i in range(0, len(cells_to_translate), batch_size):
                batch = cells_to_translate[i:i + batch_size]
                translated_batch = self.translation_engine.translate_batch(batch, i // batch_size)
                translated_cells.extend(translated_batch)

            # Reconstruct table data with translations
            cell_map = {pos: text for pos, text in zip(positions, translated_cells)}
            translated_data = [
                [cell_map.get((row_idx, col_idx), cell_text)
                 for col_idx, cell_text in enumerate(row)]
                for row_idx, row in enumerate(table['data'])
            ]

            translated_table = table.copy()
            translated_table['data'] = translated_data
            translated_tables.append(translated_table)

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
    
    def _evaluate_if_enabled(
        self,
        original_paragraphs: list,
        translated_paragraphs: list,
    ) -> Dict[str, Any]:
        """
        Run BLEU/chrF evaluation when enable_evaluation=true in config.

        Two modes:
          reference_doc set → ground-truth evaluation against provided file
          reference_doc null → back-translation proxy (translate target→source,
                               score back-translations against the original English)
        """
        if not self.config.get('enable_evaluation', False):
            return {}

        try:
            from evaluation import TranslationEvaluator, load_references
        except ImportError as e:
            logger.warning(f"Evaluation skipped: {e}")
            return {}

        evaluator = TranslationEvaluator()
        original_texts   = [p['text'] for p in original_paragraphs  if p.get('text', '').strip()]
        translated_texts = [p['text'] for p in translated_paragraphs if p.get('text', '').strip()]

        ref_path = self.config.get('reference_doc')

        if ref_path:
            try:
                references = load_references(ref_path)
                logger.info(f"Evaluating against reference file: {ref_path}")
                metrics = evaluator.evaluate_document(translated_texts, references, mode='reference')
            except FileNotFoundError:
                logger.warning(f"reference_doc not found: {ref_path} — falling back to back-translation")
                metrics = self._back_translation_eval(evaluator, original_texts, translated_texts)
        else:
            logger.info("No reference_doc set — using back-translation proxy evaluation")
            metrics = self._back_translation_eval(evaluator, original_texts, translated_texts)

        evaluator.write_report(metrics, hypotheses=translated_texts)
        return metrics

    def _back_translation_eval(
        self,
        evaluator,
        original_texts: List[str],
        translated_texts: List[str],
    ) -> Dict[str, Any]:
        """
        Back-translate a sample of translated_texts to English and score
        the result against the original English paragraphs as proxy BLEU/chrF.
        """
        sample_size = min(self.config.get('eval_back_translate_sample', 20), len(translated_texts))
        logger.info(f"Back-translating {sample_size} paragraphs for proxy evaluation…")

        sample_translated = translated_texts[:sample_size]
        sample_original   = original_texts[:sample_size]

        back_translated = self.translation_engine.back_translate_batch(
            sample_translated,
            source_lang=self.config['target_language'],
            target_lang='English',
        )

        return evaluator.evaluate_document(
            back_translated,
            sample_original,
            mode='back_translation',
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
            'target_language': self.config['target_language'],
            'translation_brief': bool(self.translation_engine._translation_brief),
        }