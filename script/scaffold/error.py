"""Errors for scaffolding."""


class ExitApp(Exception):
    """Exception to indicate app should exit."""

    def __init__(self, reason, exit_code=1):
        """Initialize the exit app exception."""
        self.reason = reason
        self.exit_code = exit_code
