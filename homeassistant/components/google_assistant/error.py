"""Errors for Google Assistant."""
from .const import ERR_CHALLENGE_NEEDED


class SmartHomeError(Exception):
    """Google Assistant Smart Home errors.

    https://developers.google.com/actions/smarthome/create-app#error_responses
    """

    def __init__(self, code, msg):
        """Log error code."""
        super().__init__(msg)
        self.code = code

    def to_response(self):
        """Convert to a response format."""
        return {"errorCode": self.code}


class ChallengeNeeded(SmartHomeError):
    """Google Assistant Smart Home errors.

    https://developers.google.com/actions/smarthome/create-app#error_responses
    """

    def __init__(self, challenge_type):
        """Initialize challenge needed error."""
        super().__init__(ERR_CHALLENGE_NEEDED, f"Challenge needed: {challenge_type}")
        self.challenge_type = challenge_type

    def to_response(self):
        """Convert to a response format."""
        return {
            "errorCode": self.code,
            "challengeNeeded": {"type": self.challenge_type},
        }
