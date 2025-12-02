"""Utility functions for sanitizing text data before database insertion."""
import re
from typing import Any, Dict, List


def sanitize_string(text: str) -> str:
    """
    Sanitize a string by removing null bytes and other problematic characters.
    
    PostgreSQL doesn't support null bytes (\u0000) in text fields.
    This function removes null bytes and other control characters that might
    cause issues with database operations.
    
    Args:
        text: Input string to sanitize
        
    Returns:
        Sanitized string with null bytes and problematic characters removed
    """
    if not isinstance(text, str):
        return text
    
    # Remove null bytes (PostgreSQL doesn't support them)
    text = text.replace('\x00', '')
    text = text.replace('\u0000', '')
    
    # Remove other problematic control characters (but keep newlines, tabs, etc.)
    # Keep: \n (0x0A), \r (0x0D), \t (0x09)
    # Remove: other control characters (0x00-0x08, 0x0B-0x0C, 0x0E-0x1F)
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', text)
    
    return text


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively sanitize all string values in a dictionary.
    
    Args:
        data: Dictionary to sanitize
        
    Returns:
        Dictionary with all string values sanitized
    """
    if not isinstance(data, dict):
        return data
    
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = sanitize_list(value)
        else:
            sanitized[key] = value
    
    return sanitized


def sanitize_list(data: List[Any]) -> List[Any]:
    """
    Recursively sanitize all string values in a list.
    
    Args:
        data: List to sanitize
        
    Returns:
        List with all string values sanitized
    """
    if not isinstance(data, list):
        return data
    
    sanitized = []
    for item in data:
        if isinstance(item, str):
            sanitized.append(sanitize_string(item))
        elif isinstance(item, dict):
            sanitized.append(sanitize_dict(item))
        elif isinstance(item, list):
            sanitized.append(sanitize_list(item))
        else:
            sanitized.append(item)
    
    return sanitized


def sanitize_node_data(node_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize node data before database insertion.
    
    This function sanitizes:
    - String fields (id, node_type, label)
    - Nested properties dictionary
    - Any other string values
    
    Args:
        node_data: Node data dictionary to sanitize
        
    Returns:
        Sanitized node data dictionary
    """
    sanitized = {}
    
    for key, value in node_data.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = sanitize_list(value)
        else:
            sanitized[key] = value
    
    return sanitized

