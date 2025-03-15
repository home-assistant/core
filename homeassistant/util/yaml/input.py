"""Deal with YAML input."""

from __future__ import annotations

from annotatedyaml.input import UndefinedSubstitution, extract_inputs, substitute

from .objects import Input

__all__ = ["Input", "UndefinedSubstitution", "extract_inputs", "substitute"]
