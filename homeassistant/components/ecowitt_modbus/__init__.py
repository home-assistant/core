"""The Ecowitt Modbus integration."""

from ecowitt_modbus import SUPPORTED_MODELS
from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError

from .const import CONF_UNIT_ID, DOMAIN
from .coordinator import EcowittConfigEntry, EcowittDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EcowittConfigEntry) -> bool:
    """Set up an Ecowitt sensor array from a config entry."""
    # Shared with any other integration on this gateway, and closed when the
    # last entry holding a unit on it unloads. These sensors only ever speak
    # RTU framing, whether reached directly or (the common case) through an
    # RTU-over-TCP serial gateway.
    try:
        unit = async_get_unit(
            hass,
            entry,
            ModbusTcpParams(
                host=entry.data[CONF_HOST], port=entry.data[CONF_PORT], framer="rtu"
            ),
            entry.data[CONF_UNIT_ID],
        )
    except HomeAssistantError as err:
        # Raised when this host/port is already held by another entry with
        # incompatible link settings -- translate it rather than letting the
        # generic exception handler take over with an unlocalized error.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    device = SUPPORTED_MODELS[entry.data[CONF_MODEL]](unit)
    coordinator = EcowittDataUpdateCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EcowittConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
