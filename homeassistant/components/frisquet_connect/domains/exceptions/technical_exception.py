class TechnicalException(Exception):
    _message: str

    def __init__(self, message: str):
        super().__init__(message)
        self._message = message
