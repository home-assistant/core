"""Helpers to check the recorder."""
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_start_setup

DATA_INSTANCE = "recorder_instance"
RECORDER_DOMAIN = "recorder"
RECORDER_BASE_SETUP_TIMEOUT = 60


async def async_ensure_recorder_is_ready(hass: HomeAssistant) -> None:
    """Ensure the recorder is ready if it was setup."""
    # If there is a database upgrade in progress the recorder
    # queue can exaust the available memory if we allow stage 2
    # to start. We wait until the upgrade is completed before
    # starting.
    if RECORDER_DOMAIN not in hass.config.components:
        return
    async with hass.timeout.async_timeout(
        RECORDER_BASE_SETUP_TIMEOUT, RECORDER_DOMAIN
    ), hass.timeout.async_freeze(RECORDER_DOMAIN):
        with async_start_setup(hass, [RECORDER_DOMAIN]):
            await hass.data[DATA_INSTANCE].async_db_ready
