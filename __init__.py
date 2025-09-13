"""Translation system package initialization."""

from config import Config
from agents import TranslationAgents, AgentFactory
from document_io import DocumentReader, DocumentWriter
from translation_engine import TranslationEngine, BatchProcessor
from translation_system import TranslationSystem
from utils import DocumentAnalyzer, PathResolver, TextCleaner

__version__ = "1.0.0"
__author__ = "Translation System Team"

__all__ = [
    'Config',
    'TranslationAgents',
    'AgentFactory',
    'DocumentReader',
    'DocumentWriter',
    'TranslationEngine',
    'BatchProcessor',
    'TranslationSystem',
    'DocumentAnalyzer',
    'PathResolver',
    'TextCleaner'
]