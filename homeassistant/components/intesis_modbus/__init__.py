"""The Intesis Modbus integration."""

from intesis_gw_modbus import MODELS, IntesisSingleUnitGateway, TemperatureFormat

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_MODEL, CONF_TEMPERATURE_FORMAT, CONF_UNIT_ID
from .coordinator import IntesisConfigEntry, IntesisCoordinator
from .helpers import create_modbus_params

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: IntesisConfigEntry) -> None:
    """Set up Intesis Modbus from a config entry."""
    unit = async_get_unit(
        hass, entry, create_modbus_params(entry.data), entry.data[CONF_UNIT_ID]
    )
    device = IntesisSingleUnitGateway(
        unit,
        brand=MODELS[entry.data[CONF_MODEL]].brand,
        temperature_format=TemperatureFormat(entry.data[CONF_TEMPERATURE_FORMAT]),
    )
    coordinator = IntesisCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: IntesisConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
