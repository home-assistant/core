"""The Modem Caller ID integration."""

from phone_modem import PhoneModem

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import EXCEPTIONS

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]

type ModemCallerIdConfigEntry = ConfigEntry[PhoneModem]


async def async_setup_entry(
    hass: HomeAssistant, entry: ModemCallerIdConfigEntry
) -> bool:
    """Set up Modem Caller ID from a config entry."""
    device = entry.data[CONF_DEVICE]
    api = PhoneModem(device)
    try:
        await api.initialize(device)
    except EXCEPTIONS as ex:
        raise ConfigEntryNotReady(f"Unable to open port: {device}") from ex

    entry.async_on_unload(api.close)

    async def _async_on_hass_stop(event: Event) -> None:
        """HA is shutting down, close modem port."""
        api.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_on_hass_stop)
    )

    entry.runtime_data = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ModemCallerIdConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
