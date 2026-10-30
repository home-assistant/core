"""Errors for translations."""

from script.hassfest.translation_data import (
    JSONDecodeErrorWithPath as JSONDecodeErrorWithPath,  # noqa: PLC0414
)


class ExitApp(Exception):
    """Exception to indicate app should exit."""

    def __init__(self, reason, exit_code=1):
        """Initialize the exit app exception."""
        self.reason = reason
        self.exit_code = exit_code


class MissingReference(Exception):
    """Exception to indicate a missing reference in translations."""

    def __init__(self, reference_key: str):
        """Initialize the missing reference exception."""
        self.reference_key = reference_key
        super().__init__(f"Missing reference key: {reference_key}")
