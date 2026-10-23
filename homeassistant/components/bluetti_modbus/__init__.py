"""Support for BLUETTI power stations over Modbus."""

from bluetti_modbus_lib import (
    AGGREGATE_SLAVE_ID,
    EXPANSION_PACK_FIRST_SLAVE_ID,
    MAX_BATTERY_PACKS,
)
from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import CONF_UNIT_ID, DOMAIN
from .coordinator import (
    BluettiModbusConfigEntry,
    BluettiModbusDataUpdateCoordinator,
    BluettiModbusRuntimeData,
)
from .device import expansion_pack, pack_summary, restricted_device
from .entity import bluetti_modbus_device_info

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: BluettiModbusConfigEntry
) -> None:
    """Set up BLUETTI Modbus from a config entry."""
    params = ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT])
    try:
        unit = async_get_unit(hass, entry, params, entry.data[CONF_UNIT_ID])
        summary_unit = async_get_unit(hass, entry, params, AGGREGATE_SLAVE_ID)
        pack_units = {
            unit_id: async_get_unit(hass, entry, params, unit_id)
            for unit_id in range(
                EXPANSION_PACK_FIRST_SLAVE_ID,
                EXPANSION_PACK_FIRST_SLAVE_ID + MAX_BATTERY_PACKS,
            )
        }
    except HomeAssistantError as err:
        # The device is already in use over different link settings, which
        # one shared connection cannot honour.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="link_settings_in_use",
            translation_placeholders={"error": str(err)},
        ) from err

    device = restricted_device(unit)
    coordinator = BluettiModbusDataUpdateCoordinator(
        hass,
        entry,
        device,
        pack_summary(summary_unit),
        {
            unit_id: expansion_pack(pack_unit)
            for unit_id, pack_unit in pack_units.items()
        },
    )
    await coordinator.async_config_entry_first_refresh()

    # Firmware versions come from the first refresh's own values - device
    # identity, so they go on DeviceInfo rather than becoming sensors.
    values = coordinator.data
    sw_version = (
        f"ARM {values['d_ver_arm']}, DSP {values['d_ver_dsp']}, "
        f"IoT {values['d_iot_ver']}"
    )

    # The first refresh only succeeds when this matches the entry's unique ID.
    serial = str(values["d_serial"])
    device_info = bluetti_modbus_device_info(
        serial, sw_version, host=entry.data[CONF_HOST]
    )
    device_entry = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **device_info
    )
    entry.runtime_data = BluettiModbusRuntimeData(
        coordinator=coordinator,
        device_info=device_info,
        device_id=device_entry.id,
        serial=serial,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: BluettiModbusConfigEntry
) -> None:
    """Unload a BLUETTI Modbus config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: BluettiModbusConfigEntry, device: dr.AnyDeviceEntry
) -> bool:
    """Allow removing an expansion pack that is no longer attached."""
    runtime_data = entry.runtime_data
    attached = {runtime_data.serial} | {
        str(values["b_serial"])
        for values in runtime_data.coordinator.pack_values.values()
    }
    return not any(
        identifier[1] in attached
        for identifier in device.identifiers
        if identifier[0] == DOMAIN
    )
