"""CrewAI agent definitions for the translation system."""

import logging
from typing import Dict, Any

# Import CrewAI components properly
try:
    from crewai.agent import Agent
except ImportError:
    try:
        from crewai import Agent
    except ImportError:
        # Fallback for different CrewAI versions
        import crewai
        Agent = crewai.Agent

logger = logging.getLogger(__name__)

class TranslationAgents:
    """Factory class for creating translation agents."""
    
    @staticmethod
    def create_translator_agent(target_language: str, llm_model: str = "ollama/mistral:7b") -> Agent:
        """Create a professional translator agent."""
        return Agent(
            role="Professional Translator",
            goal=f"Translate English text to {target_language} accurately",
            backstory=f"""You are a professional translator specializing in {target_language}. 
            Your job is to translate text while maintaining meaning and academic tone.
            
            CRITICAL RULES:
            1. Output ONLY the translated text in {target_language}
            2. Do NOT include any English text in your response
            3. Do NOT add comments, explanations, or metadata
            4. Do NOT include phrases like "Translation:" or "Here is the translation:"
            5. Just provide the pure translated text""",
            llm=llm_model,
            verbose=False,
            allow_delegation=False,
            max_iter=1
        )
    
    @staticmethod
    def create_quality_checker_agent(target_language: str, llm_model: str = "ollama/mistral:7b") -> Agent:
        """Create a quality checker agent for translations."""
        return Agent(
            role="Translation Quality Checker",
            goal=f"Review and improve translation quality for {target_language}",
            backstory=f"""You are a quality assurance specialist for {target_language} translations. 
            Your job is to review translations and suggest improvements while maintaining 
            accuracy and natural flow.
            
            FOCUS AREAS:
            1. Accuracy of meaning
            2. Natural language flow
            3. Cultural appropriateness
            4. Consistency in terminology
            5. Grammar and syntax""",
            llm=llm_model,
            verbose=False,
            allow_delegation=False,
            max_iter=1
        )
    
    @staticmethod
    def create_document_analyzer_agent(llm_model: str = "ollama/mistral:7b") -> Agent:
        """Create a document structure analyzer agent."""
        return Agent(
            role="Document Structure Analyzer",
            goal="Analyze document structure and maintain formatting during translation",
            backstory="""You are a document formatting specialist who understands how to 
            preserve document structure, formatting, and layout during translation processes.
            
            RESPONSIBILITIES:
            1. Identify document sections and their hierarchy
            2. Preserve formatting elements (bold, italic, alignment)
            3. Maintain table structures
            4. Handle special elements like images and captions
            5. Ensure consistent styling throughout""",
            llm=llm_model,
            verbose=False,
            allow_delegation=False,
            max_iter=1
        )

class AgentFactory:
    """Factory for creating configured agents based on system configuration."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.target_language = config['target_language']
        self.llm_model = config.get('llm_model', 'ollama/mistral:7b')
        
    def create_translator(self) -> Agent:
        """Create translator agent with system configuration."""
        return TranslationAgents.create_translator_agent(
            self.target_language, 
            self.llm_model
        )
    
    def create_quality_checker(self) -> Agent:
        """Create quality checker agent with system configuration."""
        return TranslationAgents.create_quality_checker_agent(
            self.target_language, 
            self.llm_model
        )
    
    def create_document_analyzer(self) -> Agent:
        """Create document analyzer agent with system configuration."""
        return TranslationAgents.create_document_analyzer_agent(self.llm_model)
    
    def get_all_agents(self) -> Dict[str, Agent]:
        """Get all configured agents."""
        return {
            'translator': self.create_translator(),
            'quality_checker': self.create_quality_checker(),
            'document_analyzer': self.create_document_analyzer()
        }