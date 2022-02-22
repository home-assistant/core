"""AIS NBP."""
import logging

_LOGGER = logging.getLogger(__name__)
DOMAIN = "ais_easy"


async def async_setup(hass, config):
    """Wstepna konfiguracja domeny, jeśli to konieczne."""
    return True


async def async_setup_entry(hass, config_entry):
    """Konfigurowanie integracji na podstawie wpisu konfiguracyjnego."""
    _LOGGER.info("async_setup_entry " + str(config_entry))
    # sensors
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    # switches
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "switch")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Usuń integrację - skasuj wpis konfiguracyjny."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, ["sensor", "switch"]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return True
