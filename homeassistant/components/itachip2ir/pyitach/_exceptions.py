"""Exceptions for pyitach."""


class ItachError(Exception):
    """Base iTach error."""


class ItachConnectionError(ItachError):
    """Connection error."""


class ItachCommandError(ItachError):
    """Command error returned by iTach."""

    def __init__(self, response: str, command: str | None = None) -> None:
        """Initialize command error."""
        self.response = response
        self.command = command
        message = (
            response
            if command is None
            else f"{response} for command: {command.strip()}"
        )
        super().__init__(message)


class ItachBusyError(ItachError):
    """iTach IR port is busy."""


class ItachIdentityError(ItachError):
    """Could not determine stable device identity."""


class ItachResponseError(ItachError):
    """Unexpected or malformed iTach response."""
