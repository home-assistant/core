"""Exceptions."""


class InvalidCrcError(Exception):
    """CRC error."""

    def __init__(self, expected_crc, message_crc):
        """Create exception."""
        self.expected_crc = expected_crc
        self.message_crc = message_crc
        self.message = f"Invalid CRC of message. Expected CRC: '{expected_crc!r}', Message CRC: '{message_crc!r}'"
        super().__init__(self.message)


class InvalidMessageError(Exception):
    """Message error."""

    def __init__(self, received_message):
        """Create exception."""
        self.received_message = received_message
        self.message = f"Invalid message '{received_message!r}'"
        super().__init__(self.message)


class CommandError(Exception):
    """General command error."""

    def __init__(self, received_message):
        """Create exception."""
        self.received_message = received_message
        self.message = f"Command error '{received_message!r}'"
        super().__init__(self.message)


class ConnectionException(Exception):
    """Error to indicate we cannot connect."""


class ExceptionResponse(Exception):
    """Error to indicate there is wrong response."""


class MicropelException(Exception):
    """Error to indicate there is general protocol error."""
