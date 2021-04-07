"""Helpers to check the recorder."""
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_start_setup

DATA_INSTANCE = "recorder_instance"
RECORDER_DOMAIN = "recorder"
RECORDER_BASE_SETUP_TIMEOUT = 60


async def async_wait_for_recorder_full_startup(hass: HomeAssistant) -> None:
    """Ensure the recorder is ready if it was setup."""
    if RECORDER_DOMAIN not in hass.config.components:
        return
    with async_start_setup(hass, [RECORDER_DOMAIN]):
        await hass.data[DATA_INSTANCE].async_db_ready
