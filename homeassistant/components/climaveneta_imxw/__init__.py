"""Platform for the climaveneta_imxw AC."""
import logging

from pymodbus.exceptions import ModbusException

from homeassistant.components.modbus import CALL_TYPE_REGISTER_HOLDING, get_hub
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_SLAVE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_HUB, DOMAIN, STATE_READ_ON_OFF_REGISTER
from .coordinator import ClimavenetaIMXWCoordinator

PLATFORMS = [Platform.CLIMATE]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""

    hub = get_hub(hass, entry.data[CONF_HUB])
    slave_id = entry.data[CONF_SLAVE]
    name = entry.data[CONF_NAME]
    try:
        result = await hub.async_pb_call(
            slave_id, STATE_READ_ON_OFF_REGISTER, 1, CALL_TYPE_REGISTER_HOLDING
        )
    except ModbusException as exception_error:
        _LOGGER.error(str(exception_error))
        raise ConfigEntryNotReady("Climaveneta iMXW device error") from exception_error

    if result is None:
        _LOGGER.error("Error reading value from Climaveneta iMXW modbus adapter")
        raise ConfigEntryNotReady("Climaveneta iMXW API timed out")

    coordinator = ClimavenetaIMXWCoordinator(hass, hub, slave_id, name)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Climaveneta_imxw config entry."""

    # our components don't have unload methods so no need to look at return values
    for platform in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(config_entry, platform)

    return True
