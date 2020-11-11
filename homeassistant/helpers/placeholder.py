"""Placeholder helpers."""
from typing import Any, Dict, Set

from homeassistant.util.yaml import Placeholder


class UndefinedSubstitution(Exception):
    """Error raised when we find a substitution that is not defined."""

    def __init__(self, placeholder: str) -> None:
        """Initialize the undefined substitution exception."""
        super().__init__(f"No substitution found for placeholder {placeholder}")
        self.placeholder = placeholder


def extract_placeholders(obj: Any) -> Set[str]:
    """Extract placeholders from a structure."""
    found: Set[str] = set()
    _extract_placeholders(obj, found)
    return found


def _extract_placeholders(obj: Any, found: Set[str]) -> None:
    """Extract placeholders from a structure."""
    if isinstance(obj, Placeholder):
        found.add(obj.name)
        return

    if isinstance(obj, list):
        for val in obj:
            _extract_placeholders(val, found)
        return

    if isinstance(obj, dict):
        for val in obj.values():
            _extract_placeholders(val, found)
        return


def substitute(obj: Any, substitutions: Dict[str, Any]) -> Any:
    """Substitute values."""
    if isinstance(obj, Placeholder):
        if obj.name not in substitutions:
            raise UndefinedSubstitution(obj.name)
        return substitutions[obj.name]

    if isinstance(obj, list):
        return [substitute(val, substitutions) for val in obj]

    if isinstance(obj, dict):
        return {key: substitute(val, substitutions) for key, val in obj.items()}

    return obj
