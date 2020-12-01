"""AIS NBP."""
import logging

_LOGGER = logging.getLogger(__name__)
DOMAIN = "ais_nbp"


async def async_setup(hass, config):
    """Wstepna konfiguracja domeny, jeśli to konieczne."""
    return True


async def async_setup_entry(hass, config_entry):
    """Konfigurowanie integracji na podstawie wpisu konfiguracyjnego."""
    _LOGGER.info("async_setup_entry " + str(config_entry))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Usuń integrację - skasuj wpis konfiguracyjny."""
    _LOGGER.info("async_unload_entry remove entities")
    hass.async_create_task(
        hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    )
    return True
