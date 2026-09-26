"""Support for BLUETTI power stations over Modbus."""

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
from .device import restricted_device
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

    device = restricted_device(unit)
    coordinator = BluettiModbusDataUpdateCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()

    # Firmware versions come from the first refresh's own values - device
    # identity, so they go on DeviceInfo rather than becoming sensors.
    values = device.values
    sw_version = (
        f"ARM {values['d_ver_arm']}, DSP {values['d_ver_dsp']}, "
        f"IoT {values['d_iot_ver']}"
    )

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
