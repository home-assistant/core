"""Support for BLUETTI power stations over Modbus.

The device is a Modbus device like any other: this integration does not own
its connection, it borrows a ``ModbusUnit`` from the ``modbus`` integration,
which shares one connection per device between everything talking to it, and
hands that unit to the ``bluetti-modbus`` library.
"""

from bluetti_modbus_lib.devices.getter import get_device
from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import CONF_UNIT_ID, DEVICE_TYPE_BALCO260, DOMAIN, EXCLUDED_FIELDS
from .coordinator import (
    BluettiModbusConfigEntry,
    BluettiModbusDataUpdateCoordinator,
    BluettiModbusRuntimeData,
)
from .entity import bluetti_modbus_device_info

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: BluettiModbusConfigEntry
) -> bool:
    """Set up BLUETTI Modbus from a config entry."""
    params = ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT])
    try:
        unit = async_get_unit(hass, entry, params, entry.data[CONF_UNIT_ID])
    except HomeAssistantError as err:
        # The device is already in use over different link settings, which
        # one shared connection cannot honour.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="link_settings_in_use",
            translation_placeholders={"error": str(err)},
        ) from err

    device = get_device(DEVICE_TYPE_BALCO260, unit)
    assert device is not None  # DEVICE_TYPE_BALCO260 is always a known device type

    # These fields belong on other platforms once they exist (see
    # EXCLUDED_FIELDS); narrowing the read plan here, not just entity
    # creation, keeps the coordinator from polling registers nothing reads.
    device.restrict_fields(
        name for name in device.field_names() if name not in EXCLUDED_FIELDS
    )

    coordinator = BluettiModbusDataUpdateCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()

    # Built once here: every entity hangs on the same device. Firmware
    # versions are read from the same first-refresh values already used for
    # entities below, not a separate read - see bluetti_modbus_device_info's
    # own docstring for why they land on sw_version instead of a sensor.
    arm_version = device.values.get("d_ver_arm")
    dsp_version = device.values.get("d_ver_dsp")
    sw_version = None
    if arm_version is not None or dsp_version is not None:
        sw_version = f"ARM {arm_version}, DSP {dsp_version}"

    assert (
        entry.unique_id is not None
    )  # the config flow always sets it to the confirmed serial
    entry.runtime_data = BluettiModbusRuntimeData(
        coordinator=coordinator,
        device_info=bluetti_modbus_device_info(entry.unique_id, sw_version),
    )
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **entry.runtime_data.device_info
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BluettiModbusConfigEntry
) -> bool:
    """Unload a BLUETTI Modbus config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
