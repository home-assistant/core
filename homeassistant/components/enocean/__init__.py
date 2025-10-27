"""Support for EnOcean devices."""

from __future__ import annotations

from home_assistant_enocean.enocean_device_type import EnOceanDeviceType
from home_assistant_enocean.enocean_id import EnOceanID
from home_assistant_enocean.gateway import EnOceanHomeAssistantGateway

from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .config_entry import EnOceanConfigEntry, EnOceanConfigRuntimeData
from .config_flow import CONF_ENOCEAN_DEVICES
from .const import (
    CONF_ENOCEAN_DEVICE_ID,
    CONF_ENOCEAN_DEVICE_NAME,
    CONF_ENOCEAN_DEVICE_TYPE_ID,
    DATA_ENOCEAN,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
) -> bool:
    """Set up an EnOcean gateway for the given config entry."""
    gateway = EnOceanHomeAssistantGateway(config_entry.data[CONF_DEVICE])
    await gateway.start()

    config_entry.runtime_data = EnOceanConfigRuntimeData(gateway=gateway)

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))
    async_cleanup_device_registry(hass=hass, entry=config_entry)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, gateway.chip_id.to_string())},
        manufacturer="EnOcean",
        name="EnOcean Gateway",
        model="TCM300/310 Transmitter",
        serial_number=gateway.chip_id.to_string(),
        sw_version=gateway.sw_version,
        hw_version=gateway.chip_version,
    )

    # add devices to gateway
    devices = config_entry.options.get(CONF_ENOCEAN_DEVICES, [])
    for device in devices:
        try:
            enocean_id = EnOceanID.from_string(device[CONF_ENOCEAN_DEVICE_ID])
            device_type_id = device[CONF_ENOCEAN_DEVICE_TYPE_ID]
            device_type: EnOceanDeviceType = (
                EnOceanDeviceType.get_supported_device_types()[device_type_id]
            )
            device_name = device.get(CONF_ENOCEAN_DEVICE_NAME, "EnOcean Device")
            LOGGER.warning(
                "Adding EnOcean device %s of type %s with name %s",
                enocean_id,
                device_type.unique_id,
                device_name,
            )

            gateway.add_device(
                enocean_id=enocean_id, device_type=device_type, device_name=device_name
            )

        except ValueError as ex:
            LOGGER.error(
                "Failed to add EnOcean device %s: %s",
                device.get(CONF_ENOCEAN_DEVICE_ID, "unknown"),
                ex,
            )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


@callback
def async_cleanup_device_registry(
    hass: HomeAssistant,
    entry: EnOceanConfigEntry,
) -> None:
    """Remove entries from device registry if device is removed."""
    device_registry = dr.async_get(hass)
    hass_devices = dr.async_entries_for_config_entry(
        registry=device_registry,
        config_entry_id=entry.entry_id,
    )

    device_ids = [
        dev["id"].upper() for dev in entry.options.get(CONF_ENOCEAN_DEVICES, [])
    ]

    for hass_device in hass_devices:
        for item in hass_device.identifiers:
            domain = item[0]
            device_id = (str(item[1]).split("-", maxsplit=1)[0]).upper()
            if domain == DOMAIN and device_id not in device_ids:
                LOGGER.debug(
                    "Removing Home Assistant device %s and associated entities for unconfigured EnOcean device %s",
                    hass_device.id,
                    device_id,
                )
                device_registry.async_update_device(
                    hass_device.id, remove_config_entry_id=entry.entry_id
                )
                break


async def async_reload_entry(hass: HomeAssistant, entry: EnOceanConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: EnOceanConfigEntry) -> bool:
    """Unload EnOcean config entry."""
    entry.runtime_data.gateway.unload()

    if unload_platforms := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        hass.data.pop(DATA_ENOCEAN)

    return unload_platforms
