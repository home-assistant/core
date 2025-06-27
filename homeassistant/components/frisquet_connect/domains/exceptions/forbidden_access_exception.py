from frisquet_connect.domains.exceptions.technical_exception import (
    TechnicalException,
)


class ForbiddenAccessException(TechnicalException):
    """Exception raised when the user is not allowed to access the resource"""

    def __init__(self, message: str):
        super().__init__(message)
