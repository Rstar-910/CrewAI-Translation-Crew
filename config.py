"""Configuration management for the translation system."""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

class Config:
    """Configuration manager for the translation system."""
    
    DEFAULT_CONFIG = {
        "target_language": "Hindi",
        "batch_size": 2,
        "input_doc": "input.docx", 
        "output_doc": "translated_paper.docx",
        "llm_model": "ollama/mistral:7b",
        "verbose": False,
        "translation_quality": "high"
    }
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file or create default."""
        try:
            with open(self.config_file, "r") as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {self.config_file}")
                return config
        except FileNotFoundError:
            logger.warning(f"{self.config_file} not found, using default configuration")
            self.create_default_config()
            return self.DEFAULT_CONFIG.copy()
    
    def create_default_config(self):
        """Create a default configuration file."""
        with open(self.config_file, "w") as f:
            yaml.dump(self.DEFAULT_CONFIG, f, default_flow_style=False)
        logger.info(f"Created sample {self.config_file} file")
    
    def get(self, key: str, default=None):
        """Get configuration value."""
        return self.config.get(key, default)
    
    def __getitem__(self, key: str):
        """Allow dictionary-style access."""
        return self.config[key]
    
    def validate_input_file(self) -> bool:
        """Validate that input file exists."""
        input_path = Path(self.config['input_doc'])
        if input_path.exists():
            return True
            
        # Try alternative locations
        possible_locations = [
            Path.cwd() / "input.docx",
            Path.home() / "Desktop" / "input.docx",
            Path.cwd() / self.config['input_doc']
        ]
        
        for location in possible_locations:
            if location.exists():
                self.config['input_doc'] = str(location)
                logger.info(f"Found input file at: {location}")
                return True
        
        logger.error(f"Input file not found at: {input_path}")
        logger.error("Please ensure your input file exists at one of these locations:")
        for loc in possible_locations:
            logger.error(f"  - {loc}")
        return False