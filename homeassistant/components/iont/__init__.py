"""Support for IONT EV chargers over Modbus TCP.

The charger is a Modbus device. This integration does not own its connection:
it borrows a ``ModbusUnit`` from the ``modbus`` integration, which shares one
connection per device between everything talking to it, and hands that unit to
the ``pyiont`` library.
"""

from modbus_connection import ModbusTcpParams
from pyiont import IontCharger, IontConnectionError, IontError

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, UNIT_ID
from .coordinator import IontConfigEntry, IontDataUpdateCoordinator
from .entity import connector_identifier

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: IontConfigEntry) -> bool:
    """Set up an IONT charger from a config entry."""
    params = ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT])
    try:
        unit = async_get_unit(hass, entry, params, UNIT_ID)
    except HomeAssistantError as err:
        # The device is already in use over different link settings, which one
        # shared connection cannot honour.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="link_settings_in_use",
            translation_placeholders={"error": str(err)},
        ) from err

    try:
        charger = await IontCharger.async_probe(unit)
    except IontConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except IontError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_iont_charger",
        ) from err

    coordinator = IontDataUpdateCoordinator(hass, entry, charger)
    await coordinator.async_config_entry_first_refresh()

    # Registered up front: a connector sub-device can only name the charger
    # it hangs off once that device has an ID.
    charger_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **coordinator.device_info
    )
    coordinator.charger_device_id = charger_device.id
    entry.runtime_data = coordinator

    _async_remove_stale_connectors(hass, entry, charger.connector_count)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _async_remove_stale_connectors(
    hass: HomeAssistant, entry: IontConfigEntry, connector_count: int
) -> None:
    """Remove the devices of connectors the charger no longer reports.

    How many connectors there are is read while setting up, so a connector
    that was taken out is gone by the time the entry loads again.
    """
    current = {(DOMAIN, entry.entry_id)}
    current.update(
        (DOMAIN, connector_identifier(entry.entry_id, number))
        for number in range(1, connector_count + 1)
    )

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not current.intersection(device.identifiers):
            device_registry.async_remove_device(device.id)


async def async_unload_entry(hass: HomeAssistant, entry: IontConfigEntry) -> bool:
    """Unload an IONT config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
