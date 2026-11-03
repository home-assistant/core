"""Constants for the Bring! integration."""

from enum import StrEnum

DOMAIN = "bring"


class BringEntityStateAttribute(StrEnum):
    """Store keys for Bring! entity state attributes."""

    ACTIVITY_UUID = "uuid"
    LAST_ACTIVITY_BY = "last_activity_by"
    PUBLIC_USER_UUID = "publicUserUuid"
