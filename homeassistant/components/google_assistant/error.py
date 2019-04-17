"""Errors for Google Assistant."""


class SmartHomeError(Exception):
    """Google Assistant Smart Home errors.

    https://developers.google.com/actions/smarthome/create-app#error_responses
    """

    def __init__(self, code, msg):
        """Log error code."""
        super().__init__(msg)
        self.code = code
