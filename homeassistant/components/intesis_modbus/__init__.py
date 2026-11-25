"""The Intesis Modbus integration."""

from intesis_gw_modbus import MODELS, IntesisSingleUnitGateway, TemperatureFormat

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_MODEL,
    CONF_TEMPERATURE_FORMAT,
    CONF_UNIT_ID,
    DOMAIN,
    TYPE_SERIAL,
)
from .coordinator import (
    IntesisConfigEntry,
    IntesisCoordinator,
    IntesisData,
    IntesisUnitCoordinator,
)
from .helpers import create_modbus_params

GATEWAY_MANUFACTURER = "Intesis (HMS Networks)"

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
    gateway = IntesisCoordinator(hass, entry, device)
    await gateway.async_config_entry_first_refresh()
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=GATEWAY_MANUFACTURER,
        model=entry.data[CONF_MODEL],
        name=entry.title,
        sw_version=device.software_version,
    )
    # An air conditioner the gateway cannot reach does not stop the setup
    air_conditioner = IntesisUnitCoordinator(hass, entry, gateway)
    await air_conditioner.async_refresh()
    entry.async_on_unload(
        gateway.async_add_listener(air_conditioner.async_follow_gateway)
    )
    entry.runtime_data = IntesisData(gateway=gateway, unit=air_conditioner)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: IntesisConfigEntry) -> None:
    """Migrate an old config entry."""
    if entry.version == 1 and entry.minor_version == 1:
        # 1.2 adds the connection type; until then every link was a serial one
        hass.config_entries.async_update_entry(
            entry, data={CONF_TYPE: TYPE_SERIAL, **entry.data}, minor_version=2
        )


async def async_unload_entry(hass: HomeAssistant, entry: IntesisConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
