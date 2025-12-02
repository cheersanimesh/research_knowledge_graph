"""LLM wrapper for OpenAI and Together AI API calls."""
import json
import logging
from typing import Optional, Dict, Any, Union, List
from openai import OpenAI
from together import Together
from config import Config

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for interacting with OpenAI and Together AI LLM APIs."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize LLM client."""
        # If model is explicitly 'openai', use default OpenAI model
        if model and model.lower() == 'openai':
            self.model = Config.OPENAI_MODEL
        else:
            self.model = model or Config.OPENAI_MODEL
        
        self._is_openai_model = self._is_openai_model_check(self.model)
        
        if self._is_openai_model:
            self.api_key = api_key or Config.OPENAI_API_KEY
            self.client: Union[OpenAI, Together] = OpenAI(api_key=self.api_key)
        else:
            # Use Together AI SDK for open source models
            self.api_key = api_key or Config.TOGETHER_API_KEY
            self.client: Union[OpenAI, Together] = Together(api_key=self.api_key)
    
    def _is_openai_model_check(self, model: str) -> bool:
        """
        Check if the model is an OpenAI model.
        
        Args:
            model: Model name to check
            
        Returns:
            True if OpenAI model, False otherwise
        """
        model_lower = model.lower()
        # Check for explicit 'openai' prefix or GPT models
        return (
            model_lower == 'openai' or
            model_lower.startswith('openai/') or
            model_lower.startswith('gpt-') or
            model_lower.startswith('gpt4') or
            model_lower.startswith('o1-')
        )
    
    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Get completion from LLM.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            response_format: Optional response format (e.g., {"type": "json_object"})
        
        Returns:
            Response text
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if response_format:
                kwargs["response_format"] = response_format
            
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            raise
    
    def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Get JSON completion from LLM.
        
        Returns:
            Parsed JSON as dictionary
        """
        response_format = {"type": "json_object"}
        response_text = self.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text}")
            raise
    
    def embed(
        self,
        text: str,
        model: Optional[str] = None
        ) -> List[float]:
        """
        Compute an embedding vector for the given text.
        For this POC we only support OpenAI embeddings.
        """
        if not self._is_openai_model:
            raise RuntimeError(
                "Embedding is only implemented for OpenAI models in this POC."
            )

        embedding_model = model or Config.OPENAI_EMBEDDING_MODEL
        try:
            resp = self.client.embeddings.create(
                model=embedding_model,
                input=text
            )
            return resp.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding API error: {e}")
            raise


