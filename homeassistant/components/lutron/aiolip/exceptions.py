"""Lutron exceptions."""

from typing import Any


class LutronException(Exception):
    """Base exception for all Lutron-related errors."""

    def __init__(self, message: str, details: Any | None = None) -> None:
        """Initialize the exception.

        Args:
            message: Error message
            details: Additional error details

        """
        super().__init__(message)
        self.message = message
        self.details = details


class LIPConnectionStateError(LutronException):
    """An exception to represent a connection state error."""

    def __init__(
        self,
        message: str = "Lutron Integration Protocol is not connected.",
        details: Any | None = None,
    ) -> None:
        """Initialize connection state error."""
        super().__init__(message, details)

    def __str__(self) -> str:
        """Return string representation."""
        return self.message


class LIPProtocolError(LutronException):
    """An exception to represent a protocol error."""

    def __init__(
        self, received: Any, expected: Any, message: str | None = None
    ) -> None:
        """Initialize protocol error.

        Args:
            received: The received value
            expected: The expected value
            message: Optional custom message

        """
        if message is None:
            message = (
                f"Lutron Protocol Error received=[{received}] expected=[{expected}]"
            )
        super().__init__(message, {"received": received, "expected": expected})
        self.received = received
        self.expected = expected

    def __str__(self) -> str:
        """Return string representation."""
        return self.message


class LutronConnectionError(LutronException):
    """Exception raised when connection to Lutron controller fails."""

    def __init__(
        self, host: str, port: int | None = None, details: Any | None = None
    ) -> None:
        """Initialize connection error.

        Args:
            host: The host that failed to connect
            port: The port that failed to connect
            details: Additional error details

        """
        message = f"Failed to connect to Lutron controller at {host}"
        if port:
            message += f":{port}"
        super().__init__(message, details)
        self.host = host
        self.port = port


class LutronAuthenticationError(LutronException):
    """Exception raised when authentication to Lutron controller fails."""

    def __init__(self, username: str, details: Any | None = None) -> None:
        """Initialize authentication error.

        Args:
            username: The username that failed authentication
            details: Additional error details

        """
        message = f"Authentication failed for user '{username}'"
        super().__init__(message, details)
        self.username = username


class LutronDatabaseError(LutronException):
    """Exception raised when loading or parsing the Lutron database fails."""

    def __init__(self, operation: str, details: Any | None = None) -> None:
        """Initialize database error.

        Args:
            operation: The operation that failed
            details: Additional error details

        """
        message = f"Database operation failed: {operation}"
        super().__init__(message, details)
        self.operation = operation


class LutronDeviceNotFoundError(LutronException):
    """Exception raised when a device is not found in the Lutron system."""

    def __init__(self, device_id: int, device_type: str | None = None) -> None:
        """Initialize device not found error.

        Args:
            device_id: The device ID that was not found
            device_type: The type of device

        """
        message = f"Device {device_id}"
        if device_type:
            message += f" ({device_type})"
        message += " not found in Lutron system"
        super().__init__(message, {"device_id": device_id, "device_type": device_type})
        self.device_id = device_id
        self.device_type = device_type


class LIPCommandError(LutronException):
    """Exception raised when a command fails to execute."""

    def __init__(
        self, command: str, device_id: int | None = None, details: Any | None = None
    ) -> None:
        """Initialize command error.

        Args:
            command: The command that failed
            device_id: The device ID the command was sent to
            details: Additional error details

        """
        message = f"Command '{command}' failed"
        if device_id:
            message += f" for device {device_id}"
        super().__init__(message, details)
        self.command = command
        self.device_id = device_id


class LutronTimeoutError(LutronException):
    """Exception raised when an operation times out."""

    def __init__(
        self, operation: str, timeout: float, details: Any | None = None
    ) -> None:
        """Initialize timeout error.

        Args:
            operation: The operation that timed out
            timeout: The timeout value in seconds
            details: Additional error details

        """
        message = f"Operation '{operation}' timed out after {timeout} seconds"
        super().__init__(message, details)
        self.operation = operation
        self.timeout = timeout
