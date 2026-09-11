"""The Coolmaster integration."""

from pycoolmasternet_async import CoolMasterNet

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_SEND_WAKEUP_PROMPT, CONF_SWING_SUPPORT, DOMAIN
from .coordinator import CoolmasterConfigEntry, CoolmasterDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CoolmasterConfigEntry) -> bool:
    """Set up Coolmaster from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    send_wakeup_prompt = entry.data.get(CONF_SEND_WAKEUP_PROMPT, False)
    if not entry.data.get(CONF_SWING_SUPPORT):
        coolmaster = CoolMasterNet(
            host,
            port,
            send_initial_line_feed=send_wakeup_prompt,
        )
    else:
        # Swing support adds an additional request per unit. The requests are
        # done in parallel, which can cause delays on the server. Therefore,
        # we increase the request timeout to 5 seconds instead of 1.
        coolmaster = CoolMasterNet(
            host,
            port,
            send_initial_line_feed=send_wakeup_prompt,
            read_timeout=5,
            swing_support=True,
        )
    try:
        info = await coolmaster.info()
        if not info:
            raise ConfigEntryNotReady
    except OSError as error:
        raise ConfigEntryNotReady from error
    coordinator = CoolmasterDataUpdateCoordinator(hass, entry, coolmaster, info)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await _async_migrate_unique_ids(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_migrate_unique_ids(
    hass: HomeAssistant, entry: CoolmasterConfigEntry
) -> None:
    """Migrate entities and devices to config-entry-scoped unique IDs.

    Unique IDs used to be the raw unit ID (e.g. L5.002). Unit IDs are only
    unique within a single CoolMasterNet device, so two devices reporting
    the same unit IDs collided and the second device's entities were
    silently dropped.
    """
    prefix = f"{entry.entry_id}-"

    @callback
    def _migrate(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        if entity_entry.unique_id.startswith(prefix):
            return None
        return {"new_unique_id": f"{prefix}{entity_entry.unique_id}"}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate)

    unit_ids = set(entry.runtime_data.data)
    dev_reg = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        new_identifiers = {
            (domain, f"{prefix}{ident}")
            if domain == DOMAIN and ident in unit_ids
            else (domain, ident)
            for domain, ident in device.identifiers
        }
        if new_identifiers != device.identifiers:
            dev_reg.async_update_device(device.id, new_identifiers=new_identifiers)
        elif not any(
            domain == DOMAIN and ident.startswith(prefix)
            for domain, ident in device.identifiers
        ):
            # The device was claimed by another config entry before unique
            # IDs were scoped per entry (identifier collision); this entry's
            # own device will be created on platform setup.
            dev_reg.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )


async def async_unload_entry(hass: HomeAssistant, entry: CoolmasterConfigEntry) -> bool:
    """Unload a Coolmaster config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: CoolmasterConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    return not device_entry.identifiers.intersection(
        (DOMAIN, f"{config_entry.entry_id}-{unit_id}")
        for unit_id in config_entry.runtime_data.data
    )
