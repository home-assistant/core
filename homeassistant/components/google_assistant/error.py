"""Errors for Google Assistant."""

from .const import CHALLENGE_ACK_NEEDED, CHALLENGE_PIN_NEEDED, ERR_CHALLENGE_NEEDED


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
        # Auto-set challenge_type based on flags if not explicitly provided
        if challenge_type is None:
            if pin_needed:
                challenge_type = CHALLENGE_PIN_NEEDED
            elif ack_needed:
                challenge_type = CHALLENGE_ACK_NEEDED
        self.challenge_type = challenge_type

    def to_response(self):
        """Convert to a response format."""
        # Le errorCode doit être exactement 'challengeNeeded'
        response = {"errorCode": "challengeNeeded"}

        # L'objet de défi doit être 'challengeNeeded' (majuscule au N)
        # et le type doit être 'ackNeeded' pour la voix
        if self.ack_needed or self.challenge_type == CHALLENGE_ACK_NEEDED:
            response["challengeNeeded"] = {"type": CHALLENGE_ACK_NEEDED}
        elif self.pin_needed or self.challenge_type == CHALLENGE_PIN_NEEDED:
            response["challengeNeeded"] = {"type": CHALLENGE_PIN_NEEDED}

        return response
