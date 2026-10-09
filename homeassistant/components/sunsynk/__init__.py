"""The Sunsynk integration."""

import asyncio

from modbus_connection import ModbusTcpParams
from sunsynk.client import SunsynkClient
from sunsynk.exceptions import SunsynkAuthenticationError, SunsynkConnectionError
from sunsynk_modbus import SunsynkInverter

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TYPE,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_UNIT_ID, TYPE_CLOUD, TYPE_MODBUS
from .coordinator import (
    SunsynkConfigEntry,
    SunsynkDataUpdateCoordinator,
    SunsynkModbusCoordinator,
)
from .entity import inverter_device_info, modbus_inverter_device_info

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SunsynkConfigEntry) -> bool:
    """Set up Sunsynk from a config entry."""
    if entry.data[CONF_TYPE] == TYPE_MODBUS:
        entry.runtime_data = await _async_setup_modbus(hass, entry)
    else:
        entry.runtime_data = await _async_setup_cloud(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_setup_cloud(
    hass: HomeAssistant, entry: SunsynkConfigEntry
) -> list[SunsynkDataUpdateCoordinator]:
    """Set up the inverters of a Sunsynk Connect account."""
    client = SunsynkClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )
    try:
        inverters = await client.get_inverters()
    except SunsynkAuthenticationError as err:
        raise ConfigEntryAuthFailed(err) from err
    except SunsynkConnectionError as err:
        raise ConfigEntryNotReady(err) from err

    coordinators = [
        SunsynkDataUpdateCoordinator(hass, entry, client, inverter)
        for inverter in inverters
    ]
    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        )
    )

    # The battery device links to its inverter, so the inverter must exist first.
    device_registry = dr.async_get(hass)
    for inverter in inverters:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **inverter_device_info(inverter)
        )
    return coordinators


async def _async_setup_modbus(
    hass: HomeAssistant, entry: SunsynkConfigEntry
) -> SunsynkModbusCoordinator:
    """Set up an inverter that uses Modbus TCP."""
    serial_number = entry.unique_id
    assert serial_number is not None
    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]),
        entry.data[CONF_UNIT_ID],
    )
    coordinator = SunsynkModbusCoordinator(
        hass, entry, SunsynkInverter(unit), serial_number
    )
    await coordinator.async_config_entry_first_refresh()

    # The battery device links to its inverter, so the inverter must exist first.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **modbus_inverter_device_info(serial_number)
    )
    return coordinator


async def async_unload_entry(hass: HomeAssistant, entry: SunsynkConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: SunsynkConfigEntry) -> bool:
    """Migrate an old config entry."""
    if entry.minor_version == 1:
        # All entries from before Modbus support connect to the cloud.
        hass.config_entries.async_update_entry(
            entry, data={CONF_TYPE: TYPE_CLOUD, **entry.data}, minor_version=2
        )
    return True
