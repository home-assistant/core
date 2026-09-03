"""Custom exceptions for the Community store."""


class StoreError(Exception):
    """Super basic."""


class RepositoryArchivedError(StoreError):
    """For repositories that are archived."""


class NotModifiedError(StoreError):
    """For responses that are not modified."""


class ExpectedError(StoreError):
    """For stuff that are expected."""


class RepositoryExistsError(StoreError):
    """For repositories that already exist."""


class ExecutionInProgressError(StoreError):
    """Exception to raise if execution is still in progress."""


class AppRepositoryError(StoreError):
    """Exception to raise when user tries to add an app repository."""

    exception_message = (
        "The repository does not seem to be an integration, "
        "but an app repository. The Community store does not manage apps."
    )

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__(self.exception_message)


class CoreRepositoryError(StoreError):
    """Exception to raise when user tries to add the home-assistant/core repository."""

    exception_message = (
        "You can not add homeassistant/core, to use core integrations "
        "check the Home Assistant documentation for how to add them."
    )

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__(self.exception_message)
