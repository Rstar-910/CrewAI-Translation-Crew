"""Core translation engine using CrewAI."""

from __future__ import annotations

import logging
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from crewai import Task, Crew, Process

from agents import AgentFactory
from utils import TextCleaner

logger = logging.getLogger(__name__)

class TranslationEngine:
    """Core translation engine using CrewAI agents and Ollama."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.text_cleaner = TextCleaner()
        self.agent_factory = AgentFactory(config)
        self.translator_agent = self.agent_factory.create_translator()
        self.quality_checker_agent = self.agent_factory.create_quality_checker()
        self.document_analyzer_agent = self.agent_factory.create_document_analyzer()
        self._translation_brief: str = ""  # populated by analyze_document()

    def analyze_document(self, paragraphs: List[Dict[str, Any]]) -> str:
        """
        Run the Document Analyzer agent once on a sample of the document.
        Produces a Translation Brief — domain, key terms, proper nouns, register —
        which is then injected into every Translator task as context.
        """
        sample_size = self.config.get('analysis_sample_size', 15)
        sample_texts = [
            p['text'] for p in paragraphs if p.get('text', '').strip()
        ][:sample_size]

        if not sample_texts:
            logger.info("No content to analyze — skipping pre-translation document analysis")
            return ""

        sample = "\n\n".join(f"{i + 1}. {t}" for i, t in enumerate(sample_texts))
        target = self.config['target_language']

        analysis_task = Task(
            description=f"""
            Analyze the following excerpt from a document that will be translated from English
            to {target}. Produce a structured TRANSLATION BRIEF for the translator.

            DOCUMENT EXCERPT:
            {sample}

            Your brief must cover:
            1. Document type and domain (e.g. academic, legal, medical, religious, technical)
            2. Register and tone (formal, informal, scholarly, conversational)
            3. Key domain-specific terms — provide recommended {target} equivalents
            4. Proper nouns (people, places, organisations, scripture references) —
               state whether each should be transliterated or has an established {target} form
            5. Recurring phrases or idioms that need consistent treatment
            6. Any cultural context the translator should be aware of

            Format the output as a clear, structured TRANSLATION BRIEF with labelled sections.
            """,
            agent=self.document_analyzer_agent,
            expected_output=(
                f"Structured Translation Brief with domain, register, key terms, "
                f"proper nouns and cultural notes for English → {target} translation"
            )
        )

        crew = Crew(
            agents=[self.document_analyzer_agent],
            tasks=[analysis_task],
            verbose=self.config.get('verbose', True),
            process=Process.sequential,
        )

        try:
            result = crew.kickoff()
            brief = str(result).strip()
            logger.info("Document analysis complete. Translation brief generated.")
            self._translation_brief = brief
            return brief
        except Exception as e:
            logger.warning(f"Document analysis failed: {e} — proceeding without brief")
            self._translation_brief = ""
            return ""

    def translate_batch(self, batch_texts: List[str], batch_index: int) -> List[str]:
        """
        Translate a batch via a two-agent CrewAI pipeline:
          Agent 1 — Professional Translator  : produces the initial translation
          Agent 2 — Translation Quality Checker : reviews and refines it
        """
        logger.info(f"Translating batch {batch_index + 1} with {len(batch_texts)} paragraphs")

        numbered_texts = [
            f"{i}. {text}" for i, text in enumerate(batch_texts, 1) if text.strip()
        ]
        if not numbered_texts:
            return batch_texts

        batch_text = "\n\n".join(numbered_texts)
        translate_task = self._create_translation_task(batch_text)
        quality_task = self._create_quality_check_task(translate_task)

        crew = Crew(
            agents=[self.translator_agent, self.quality_checker_agent],
            tasks=[translate_task, quality_task],
            verbose=self.config.get('verbose', True),
            process=Process.sequential,
        )

        try:
            result = crew.kickoff()
            return self._parse_translation_result(result, batch_texts)
        except Exception as e:
            logger.error(f"Error translating batch {batch_index + 1}: {type(e).__name__}: {str(e)}")
            logger.error("Returning original text as fallback — check Ollama is running: ollama serve")
            return batch_texts
    
    def _create_translation_task(self, batch_text: str) -> Task:
        """Create a translation task for the given batch text."""
        quality_instructions = {
            'high': (
                "Preserve all academic and technical terminology precisely. "
                "Maintain a formal register and ensure cultural nuance is respected."
            ),
            'medium': (
                "Ensure accurate meaning transfer with natural, readable phrasing."
            ),
            'low': (
                "Provide a quick translation focusing on core meaning over stylistic precision."
            ),
        }
        quality = self.config.get('translation_quality', 'high')
        quality_note = quality_instructions.get(quality, quality_instructions['high'])

        brief_section = (
            f"\n\nTRANSLATION BRIEF (follow these guidelines for terminology and context):\n"
            f"{self._translation_brief}"
            if self._translation_brief else ""
        )

        return Task(
            description=f"""
            Translate the following English text to {self.config['target_language']}:

            {batch_text}
            {brief_section}

            Requirements:
            - Translate each numbered paragraph separately
            - Output format: Return each translation on separate lines, maintaining the same numbering
            - Only provide the {self.config['target_language']} translation
            - Do not add any English text, comments, or explanations
            - Quality guideline: {quality_note}
            """,
            agent=self.translator_agent,
            expected_output=f"Numbered list of paragraphs translated to {self.config['target_language']}"
        )
    
    def _create_quality_check_task(self, translate_task: Task) -> Task:
        """Create a quality-review task that refines the Translator's output."""
        return Task(
            description=f"""
            Review the {self.config['target_language']} translation produced by the Translator.

            Your job:
            1. Check that the meaning of every sentence is accurately preserved
            2. Ensure natural {self.config['target_language']} language flow and correct grammar
            3. Verify cultural appropriateness and consistent terminology
            4. Keep the exact numbered format (1. 2. 3. ...) unchanged
            5. If a translation is already accurate and fluent, return it as-is
            6. Output ONLY the final {self.config['target_language']} text — no English, no comments
            """,
            agent=self.quality_checker_agent,
            context=[translate_task],
            expected_output=(
                f"Reviewed and polished numbered list of paragraphs in "
                f"{self.config['target_language']}"
            )
        )

    def back_translate_batch(
        self, texts: List[str], source_lang: str, target_lang: str
    ) -> List[str]:
        """
        Translate texts from source_lang back to target_lang.
        Used for proxy evaluation when no reference file is available —
        back-translates to English then scores against the original.
        """
        numbered = [f"{i}. {t}" for i, t in enumerate(texts, 1) if t.strip()]
        if not numbered:
            return texts

        batch_text = "\n\n".join(numbered)

        task = Task(
            description=f"""
            Translate the following {source_lang} text to {target_lang}.

            {batch_text}

            Requirements:
            - Translate each numbered item separately
            - Maintain the same numbering (1. 2. 3. …)
            - Output only {target_lang} text — no comments or explanations
            """,
            agent=self.translator_agent,
            expected_output=f"Numbered list of texts translated to {target_lang}",
        )

        crew = Crew(
            agents=[self.translator_agent],
            tasks=[task],
            verbose=False,
            process=Process.sequential,
        )

        try:
            result = crew.kickoff()
            return self._parse_translation_result(result, texts)
        except Exception as e:
            logger.warning(f"Back-translation failed: {e}")
            return texts

    def _parse_translation_result(self, result, batch_texts: List[str]) -> List[str]:
        """Parse the translation result and align with input texts."""
        cleaned_result = self.text_cleaner.clean_translation_result(result)
        
        # Parse the numbered results
        translated_texts = []
        current_text = ""
        
        for line in cleaned_result.split('\n'):
            line = line.strip()
            if re.match(r'^\d+\.', line):  # Line starts with number and dot
                if current_text:
                    translated_texts.append(current_text.strip())
                current_text = re.sub(r'^\d+\.\s*', '', line)
            elif current_text:
                if line:  # Only add non-empty lines
                    current_text += " " + line
        
        if current_text:
            translated_texts.append(current_text.strip())
        
        # Ensure we have the same number of translations as inputs
        return self._align_translations_with_inputs(translated_texts, batch_texts)
    
    def _align_translations_with_inputs(self, translated_texts: List[str], 
                                      batch_texts: List[str]) -> List[str]:
        """Align translated texts with input texts, handling empty paragraphs."""
        result_translations = []
        translated_index = 0
        
        for original_text in batch_texts:
            if original_text.strip():  # Non-empty text
                if translated_index < len(translated_texts):
                    result_translations.append(translated_texts[translated_index])
                    translated_index += 1
                else:
                    result_translations.append(original_text)  # Fallback to original
            else:
                result_translations.append(original_text)  # Keep empty text as-is
        
        return result_translations

class BatchProcessor:
    """Handles batch processing of translations — sequential or parallel."""

    def __init__(self, translation_engine: TranslationEngine):
        self.engine = translation_engine
        self.config = translation_engine.config

    def process_paragraphs(self, paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Dispatch to parallel or sequential processing based on config."""
        if self.config.get('async_batch', False):
            return self._process_parallel(paragraphs)
        return self._process_sequential(paragraphs)

    # ------------------------------------------------------------------
    # Sequential path (original behaviour)
    # ------------------------------------------------------------------

    def _process_sequential(self, paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        batch_size = self.config.get('batch_size', 3)
        total_batches = (len(paragraphs) + batch_size - 1) // batch_size
        translated_paragraphs: List[Dict[str, Any]] = []

        logger.info(f"Processing {len(paragraphs)} paragraphs in {total_batches} batches (sequential)")

        for i in range(0, len(paragraphs), batch_size):
            batch = paragraphs[i:i + batch_size]
            batch_index = i // batch_size
            logger.info(f"Processing batch {batch_index + 1}/{total_batches}")
            translated_paragraphs.extend(self._translate_batch_to_paragraphs(batch, batch_index))
            time.sleep(self.config.get('batch_delay', 1))

        logger.info(f"Completed processing {len(translated_paragraphs)} paragraphs")
        return translated_paragraphs

    # ------------------------------------------------------------------
    # Parallel path (ThreadPoolExecutor)
    # ------------------------------------------------------------------

    def _process_parallel(self, paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        batch_size = self.config.get('batch_size', 3)
        max_workers = self.config.get('max_workers', 3)

        batches = [
            (idx, paragraphs[i:i + batch_size])
            for idx, i in enumerate(range(0, len(paragraphs), batch_size))
        ]
        total_batches = len(batches)
        results: List[List[Dict[str, Any]]] = [[] for _ in batches]

        logger.info(
            f"Processing {len(paragraphs)} paragraphs in {total_batches} batches "
            f"(parallel, max_workers={max_workers})"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self._translate_batch_to_paragraphs, batch, batch_idx): batch_idx
                for batch_idx, batch in batches
            }
            completed = 0
            for future in as_completed(future_to_idx):
                batch_idx = future_to_idx[future]
                completed += 1
                try:
                    results[batch_idx] = future.result()
                    logger.info(f"Batch {batch_idx + 1}/{total_batches} done ({completed}/{total_batches} total)")
                except Exception as e:
                    logger.error(f"Batch {batch_idx + 1} failed: {e} — keeping originals")
                    results[batch_idx] = list(batches[batch_idx][1])

        translated_paragraphs = [p for batch_result in results for p in batch_result]
        logger.info(f"Completed processing {len(translated_paragraphs)} paragraphs")
        return translated_paragraphs

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _translate_batch_to_paragraphs(self, batch: List[Dict[str, Any]],
                                        batch_index: int) -> List[Dict[str, Any]]:
        """Translate one batch and return updated paragraph dicts."""
        batch_texts = [p['text'] for p in batch]
        translated_texts = self.engine.translate_batch(batch_texts, batch_index)

        result = []
        for j, translated_text in enumerate(translated_texts):
            if j < len(batch):
                new_para = batch[j].copy()
                new_para['text'] = translated_text
                result.append(new_para)
                self._log_translation_sample(new_para, batch_index * len(batch) + j + 1)
        return result

    def _log_translation_sample(self, paragraph: Dict[str, Any], index: int):
        text = paragraph['text']
        if text.strip() and not paragraph.get('has_image', False):
            sample = text[:100] + "..." if len(text) > 100 else text
            logger.info(f"Sample translation {index}: {sample}")
        elif paragraph.get('has_image', False):
            if text.strip():
                logger.info(f"Paragraph {index}: image + text: {text[:50]}...")
            else:
                logger.info(f"Paragraph {index}: image-only paragraph")