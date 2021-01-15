"""Deal with YAML input."""

from typing import Any, Dict, Set

from .objects import Input


class UndefinedSubstitution(Exception):
    """Error raised when we find a substitution that is not defined."""

    def __init__(self, input_name: str) -> None:
        """Initialize the undefined substitution exception."""
        super().__init__(f"No substitution found for input {input_name}")
        self.input = input


def extract_inputs(obj: Any) -> Set[str]:
    """Extract input from a structure."""
    found: Set[str] = set()
    _extract_inputs(obj, found)
    return found


def _extract_inputs(obj: Any, found: Set[str]) -> None:
    """Extract input from a structure."""
    if isinstance(obj, Input):
        found.add(obj.name)
        return

    if isinstance(obj, list):
        for val in obj:
            _extract_inputs(val, found)
        return

    if isinstance(obj, dict):
        for val in obj.values():
            _extract_inputs(val, found)
        return


def substitute(obj: Any, substitutions: Dict[str, Any]) -> Any:
    """Substitute values."""
    if isinstance(obj, Input):
        if obj.name not in substitutions:
            raise UndefinedSubstitution(obj.name)
        return substitutions[obj.name]

    if isinstance(obj, list):
        return [substitute(val, substitutions) for val in obj]

    if isinstance(obj, dict):
        return {key: substitute(val, substitutions) for key, val in obj.items()}

    return obj
