"""The iZone integration."""

import pizone
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EXCLUDE, CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DATA_CONFIG, DOMAIN
from .coordinator import IZoneConfigEntry, IZoneCoordinator
from .discovery import async_ensure_discovery, async_stop_discovery

PLATFORMS = [Platform.CLIMATE]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_EXCLUDE, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the iZone component config."""
    if conf := config.get(DOMAIN):
        hass.data[DATA_CONFIG] = conf

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: IZoneConfigEntry) -> bool:
    """Set up from a config entry."""
    if CONF_HOST not in entry.data:
        raise ConfigEntryError("iZone config entry is missing host")

    uid = entry.unique_id
    if not isinstance(uid, str):
        raise ConfigEntryError("iZone config entry is missing unique_id")

    host: str = entry.data[CONF_HOST]

    try:
        discovery = await async_ensure_discovery(hass)
    except OSError as err:
        raise ConfigEntryNotReady("iZone discovery service failed to start") from err

    @callback
    def _async_on_address_changed(endpoint: pizone.ControllerEndpoint) -> None:
        if endpoint.host == entry.data[CONF_HOST]:
            return
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_HOST: endpoint.host},
        )

    try:
        controller = await discovery.create_controller(
            uid,
            host,
            on_address_changed=_async_on_address_changed,
        )
    except pizone.UnpairedBridgeError as err:
        raise ConfigEntryError(
            "iZone bridge is not paired with an air conditioner"
        ) from err
    except ConnectionError as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to iZone controller at {host}"
        ) from err
    except pizone.ControllerCommandError as err:
        raise ConfigEntryError(f"iZone controller at {host} rejected setup") from err

    coordinator = IZoneCoordinator(hass, entry, controller)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await controller.close()
        raise

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: IZoneConfigEntry) -> bool:
    """Migrate old config entry schema to the current version."""
    if entry.version == 1:
        # Clear legacy data only.
        # Raising ConfigEntryNotReady from async_migrate_entry would permanently land
        # the entry in MIGRATION_ERROR with no retry path.
        hass.config_entries.async_update_entry(entry, version=2, data={})
        return True
    return False


async def async_unload_entry(hass: HomeAssistant, entry: IZoneConfigEntry) -> bool:
    """Unload the config entry and release the controller."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = entry.runtime_data
        await coordinator.async_shutdown()
        await coordinator.controller.close()
        if not hass.config_entries.async_loaded_entries(DOMAIN):
            await async_stop_discovery(hass)
    return unload_ok
