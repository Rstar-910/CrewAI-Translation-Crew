"""Core translation engine using CrewAI."""

import logging
import time
import re
from typing import List, Dict, Any

# Import CrewAI components properly
try:
    from crewai.task import Task
    from crewai.crew import Crew
    from crewai.process import Process
except ImportError:
    try:
        from crewai import Task, Crew, Process
    except ImportError:
        # Fallback for different CrewAI versions
        import crewai
        Task = crewai.Task
        Crew = crewai.Crew
        Process = crewai.Process

from agents import AgentFactory
from utils import TextCleaner

logger = logging.getLogger(__name__)

class TranslationEngine:
    """Core translation engine that handles batch translation with CrewAI."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.agent_factory = AgentFactory(config)
        self.translator_agent = self.agent_factory.create_translator()
        self.text_cleaner = TextCleaner()
    
    def translate_batch(self, batch_texts: List[str], batch_index: int) -> List[str]:
        """Translate a batch of texts using CrewAI."""
        logger.info(f"Translating batch {batch_index + 1} with {len(batch_texts)} paragraphs")
        
        # Create numbered texts for translation
        numbered_texts = []
        for i, text in enumerate(batch_texts, 1):
            if text.strip():  # Only include non-empty texts
                numbered_texts.append(f"{i}. {text}")
        
        if not numbered_texts:
            return batch_texts  # Return original if nothing to translate
        
        batch_text = "\n\n".join(numbered_texts)
        
        # Create translation task
        translate_task = self._create_translation_task(batch_text)
        
        # Execute translation
        crew = Crew(
            agents=[self.translator_agent],
            tasks=[translate_task],
            verbose=self.config.get('verbose', False),
            process=Process.sequential
        )
        
        try:
            result = crew.kickoff()
            return self._parse_translation_result(result, batch_texts)
            
        except Exception as e:
            logger.error(f"Error translating batch {batch_index + 1}: {str(e)}")
            # Return original texts if translation fails
            return batch_texts
    
    def _create_translation_task(self, batch_text: str) -> Task:
        """Create a translation task for the given batch text."""
        return Task(
            description=f"""
            Translate the following English text to {self.config['target_language']}:

            {batch_text}

            Requirements:
            - Translate each numbered paragraph separately
            - Output format: Return each translation on separate lines, maintaining the same numbering
            - Only provide the {self.config['target_language']} translation
            - Do not add any English text, comments, or explanations
            """,
            agent=self.translator_agent,
            expected_output=f"Numbered list of paragraphs translated to {self.config['target_language']}"
        )
    
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
    """Handles batch processing of translations with progress tracking."""
    
    def __init__(self, translation_engine: TranslationEngine):
        self.engine = translation_engine
        self.config = translation_engine.config
    
    def process_paragraphs(self, paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process paragraphs in batches and return translated results."""
        batch_size = self.config.get('batch_size', 3)
        translated_paragraphs = []
        total_batches = (len(paragraphs) + batch_size - 1) // batch_size
        
        logger.info(f"Processing {len(paragraphs)} paragraphs in {total_batches} batches")
        
        for i in range(0, len(paragraphs), batch_size):
            batch = paragraphs[i:i+batch_size]
            batch_texts = [p['text'] for p in batch]
            batch_index = i // batch_size
            
            logger.info(f"Processing batch {batch_index + 1}/{total_batches}")
            
            # Translate the batch
            translated_texts = self.engine.translate_batch(batch_texts, batch_index)
            
            # Update paragraph structures with translations
            for j, translated_text in enumerate(translated_texts):
                if j < len(batch):
                    new_para = batch[j].copy()
                    new_para['text'] = translated_text
                    translated_paragraphs.append(new_para)
                    
                    # Log a sample for verification
                    self._log_translation_sample(new_para, i + j + 1)
            
            # Small delay between batches to avoid overwhelming the model
            time.sleep(self.config.get('batch_delay', 1))
        
        logger.info(f"Completed processing {len(translated_paragraphs)} paragraphs")
        return translated_paragraphs
    
    def _log_translation_sample(self, paragraph: Dict[str, Any], index: int):
        """Log a sample of the translation for verification."""
        text = paragraph['text']
        
        if len(text.strip()) > 0 and not paragraph.get('has_image', False):
            sample = text[:100] + "..." if len(text) > 100 else text
            logger.info(f"Sample translation {index}: {sample}")
        elif paragraph.get('has_image', False):
            if text.strip():
                logger.info(f"Paragraph {index}: Contains image + text: {text[:50]}...")
            else:
                logger.info(f"Paragraph {index}: Image-only paragraph")