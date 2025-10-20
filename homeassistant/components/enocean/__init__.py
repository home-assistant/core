"""Support for EnOcean devices."""

from __future__ import annotations

from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .config_entry import EnOceanConfigEntry, EnOceanConfigRuntimeData
from .config_flow import CONF_ENOCEAN_DEVICES
from .const import DATA_ENOCEAN, DOMAIN, LOGGER, PLATFORMS
from .dongle import EnOceanDongle


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
) -> bool:
    """Set up an EnOcean dongle for the given entry."""
    usb_dongle = EnOceanDongle(hass, config_entry.data[CONF_DEVICE])
    await usb_dongle.async_setup()

    # PLAN IS TO move the following instead into the config_entry's runtime_data
    config_entry.runtime_data = EnOceanConfigRuntimeData(gateway=usb_dongle)

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))
    async_cleanup_device_registry(hass=hass, entry=config_entry)

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
