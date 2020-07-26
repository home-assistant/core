"""Services for the Flow by Moen integration."""
from typing import Optional

from homeassistant.helpers.typing import HomeAssistantType


async def async_set_mode_home(
    hass: HomeAssistantType, device_id: Optional[str], location_id: Optional[str]
):
    """Set the Flo device to home mode."""


async def async_set_mode_away(
    hass: HomeAssistantType, device_id: Optional[str], location_id: Optional[str]
):
    """Set the Flo device to away mode."""


async def async_set_mode_sleep(
    hass: HomeAssistantType, device_id: Optional[str], location_id: Optional[str]
):
    """Set the Flo device to sleep mode."""


async def async_run_health_test(hass: HomeAssistantType, device_id: str):
    """Set the Flo device to sleep mode."""
