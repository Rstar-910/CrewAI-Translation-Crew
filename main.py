"""Main entry point for the translation system."""

import os
import sys
import logging
from pathlib import Path

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
        logging.FileHandler('translation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure environment for efficient models on L4 GPU
os.environ["LITELLM_LOG"] = "INFO"  # Reduced verbosity
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

def main():
    """Main execution function."""
    try:
        # Load configuration
        config_manager = Config()
        logger.info(f"Configuration loaded: {config_manager.config}")
        
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
    logger.info(f"✓ Status: {result['status']}")
    logger.info(f"✓ Target Language: {result['target_language']}")
    logger.info(f"✓ Output file: {result['output_file']}")
    logger.info(f"✓ Paragraphs translated: {result['paragraphs_translated']}/{result['total_paragraphs']}")
    logger.info(f"✓ Tables processed: {result['tables_translated']}")
    logger.info(f"✓ Images preserved: {result['images_preserved']}")
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
