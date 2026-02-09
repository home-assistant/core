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
    """Google Assistant Smart Home challenge needed error."""

    def __init__(self, ack_needed=False, pin_needed=False, challenge_type=None):
        """Initialize challenge needed error."""
        super().__init__(ERR_CHALLENGE_NEEDED, "Challenge needed")
        self.ack_needed = ack_needed
        self.pin_needed = pin_needed
        self.challenge_type = challenge_type

    def to_response(self):
        """Convert to a response format."""
        # Le errorCode doit être exactement 'challengeNeeded'
        response = {"errorCode": "challengeNeeded"}

        # L'objet de défi doit être 'challengeNeeded' (majuscule au N)
        # et le type doit être 'ackNeeded' pour la voix
        if self.ack_needed or self.challenge_type == "ackNeeded":
            response["challengeNeeded"] = {"type": "ackNeeded"}
        elif self.pin_needed or self.challenge_type == "pinNeeded":
            response["challengeNeeded"] = {"type": "pinNeeded"}

        return response
