"""Main entry point for the translation system."""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Windows consoles default to cp1252 which cannot encode Devanagari/Hindi.
# Reconfigure stdout/stderr to UTF-8 so log messages with Hindi text don't crash.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add current directory to Python path to enable imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from translation_system import TranslationSystem
    from config import Config
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure all files are in the same directory and dependencies are installed.")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('translation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

os.environ["LITELLM_LOG"] = "INFO"

def main():
    """Main execution function."""
    try:
        # Load configuration
        config_manager = Config()
        logger.info(f"Configuration loaded: {config_manager.config}")

        # Optionally restrict visible GPUs based on config
        cuda_device = config_manager.config.get('cuda_device')
        if cuda_device is not None:
            os.environ["CUDA_VISIBLE_DEVICES"] = str(cuda_device)
        
        # Verify input file exists
        if not config_manager.validate_input_file():
            return
        
        # Create and run translation system
        translation_system = TranslationSystem(config_manager.config)
        result = translation_system.run_translation()
        
        # Print summary
        print_translation_summary(result)
        
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
        raise

def print_translation_summary(result: dict):
    """Print a formatted translation summary."""
    logger.info("=" * 50)
    logger.info("TRANSLATION SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Status             : {result['status']}")
    logger.info(f"Target Language    : {result['target_language']}")
    logger.info(f"Output file        : {result['output_file']}")
    logger.info(f"Translation Brief  : {'generated' if result.get('translation_brief') else 'not generated'}")
    logger.info(f"Paragraphs         : {result['paragraphs_translated']}/{result['total_paragraphs']}")
    logger.info(f"Tables             : {result['tables_translated']}")
    logger.info(f"Images preserved   : {result['images_preserved']}")

    eval_metrics = result.get('evaluation', {})
    if eval_metrics.get('bleu') is not None:
        logger.info(f"BLEU Score         : {eval_metrics['bleu']:.2f}  ({eval_metrics.get('bleu_interpretation', '')})")
        logger.info(f"chrF Score         : {eval_metrics['chrf']:.2f}  ({eval_metrics.get('chrf_interpretation', '')})")
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
