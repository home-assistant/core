"""The Profalux Neosol integration."""

from pyneosol import NeosolError

from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER
from .coordinator import NeosolConfigEntry, NeosolCoordinator, open_dongle

PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: NeosolConfigEntry) -> bool:
    """Set up Profalux Neosol from a config entry."""
    port = entry.data[CONF_DEVICE]

    try:
        dongle, info = await open_dongle(port)
    except NeosolError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"port": port, "error": str(err)},
        ) from err

    coordinator = NeosolCoordinator(hass, entry, dongle, info)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await dongle.close()
        raise

    entry.runtime_data = coordinator

    # The shutters are attached to this device through `via_device`, so it has to exist
    # before the platforms add their entities.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, info.serial_number)},
        manufacturer=MANUFACTURER,
        translation_key="dongle",
        hw_version=info.hardware_version,
        sw_version=info.software_version,
        serial_number=info.serial_number,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeosolConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await entry.runtime_data.dongle.close()

    return unload_ok
