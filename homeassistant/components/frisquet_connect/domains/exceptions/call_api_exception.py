from frisquet_connect.domains.exceptions.technical_exception import (
    TechnicalException,
)


class CallApiException(TechnicalException):
    """Exception raised when calling the API"""

    def __init__(self, message: str):
        super().__init__(message)
