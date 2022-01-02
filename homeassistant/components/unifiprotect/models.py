"""The unifiprotect integration models."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProtectRequiredKeysMixin:
    """Mixin for required keys."""

    ufp_required_field: str | None = None
    ufp_value: str | None = None
