"""Sonos specific exceptions."""

from homeassistant.components.media_player.errors import BrowseError
from homeassistant.exceptions import HomeAssistantError


class UnknownMediaType(BrowseError):
    """Unknown media type."""


class SonosSubscriptionsFailed(HomeAssistantError):
    """Subscription creation failed."""


class SonosUpdateError(HomeAssistantError):
    """Update failed."""


class S1BatteryMissing(SonosUpdateError):
    """Battery update failed on S1 firmware."""
