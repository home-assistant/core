"""The TIS Control integration."""

from tis_smartbus import TISConnectionError, TISGateway

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .hub import TISHub

PLATFORMS: list[Platform] = [Platform.LIGHT]

type TISConfigEntry = ConfigEntry[TISHub]


async def async_setup_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    """Set up TIS Control from a config entry."""
    gateway = TISGateway(entry.data[CONF_HOST], entry.data[CONF_PORT])
    try:
        await gateway.connect()
    except TISConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err
    hub = TISHub(hass, entry, gateway, entry.data[CONF_DEVICES])
    try:
        await hub.async_start()
    except TISConnectionError as err:
        await hub.async_stop()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
    return unload_ok
