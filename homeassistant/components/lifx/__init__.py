"""Support for LIFX."""

from lifx import Device, LifxError
import voluptuous as vol

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SERIAL, DATA_LIFX_MANAGER, DOMAIN, LOGGER
from .coordinator import LIFXConfigEntry, LIFXUpdateCoordinator
from .discovery import async_setup_discovery
from .entity import async_repair_device_registry
from .manager import LIFXManager
from .migration import async_migrate_serials
from .util import async_resolve_host, normalize_serial

CONF_SERVER = "server"
CONF_BROADCAST = "broadcast"


INTERFACE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SERVER): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_BROADCAST): cv.string,
    }
)

CONFIG_SCHEMA = vol.All(
    cv.deprecated(DOMAIN),
    vol.Schema(
        {
            DOMAIN: {
                LIGHT_DOMAIN: vol.Schema(vol.All(cv.ensure_list, [INTERFACE_SCHEMA]))
            }
        },
        extra=vol.ALLOW_EXTRA,
    ),
)


# The select platform names the number entity that supersedes it, so the number
# entity has to be registered before the platforms that look it up are set up
NUMBER_PLATFORM = [Platform.NUMBER]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LIFX component."""
    manager = LIFXManager(hass)
    hass.data[DATA_LIFX_MANAGER] = manager
    manager.async_setup()
    async_setup_discovery(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: LIFXConfigEntry) -> bool:
    """Migrate a LIFX config entry to version 2."""
    if entry.unique_id is None or entry.unique_id == DOMAIN:
        # The shared entry that predates one entry per device holds no host for
        # any of them, so there is nothing to migrate with: it is dropped and
        # its devices are offered again by discovery, which is how they were
        # found in the first place
        LOGGER.debug("Removing the legacy LIFX config entry %s", entry.entry_id)
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return False

    await async_migrate_serials(hass, entry)
    try:
        serial = normalize_serial(entry.unique_id)
    except ValueError as err:
        # Nothing can make the entry usable, so it is left for the user to
        # remove rather than retried
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_serial",
            translation_placeholders={"unique_id": entry.unique_id},
        ) from err
    hass.config_entries.async_update_entry(
        entry,
        unique_id=serial,
        data={
            CONF_HOST: entry.data[CONF_HOST],
            CONF_SERIAL: serial,
        },
        version=2,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LIFXConfigEntry) -> bool:
    """Set up LIFX from a config entry."""
    assert entry.unique_id is not None
    host = entry.data[CONF_HOST]
    try:
        # An entry created before the migration to lifx-async can hold a
        # hostname, which the library rejects, so it is resolved every time
        # rather than rewritten into the entry behind the user's back
        device = await Device.connect(
            ip=await async_resolve_host(hass, host), serial=entry.data[CONF_SERIAL]
        )
    # An unresolvable hostname raises OSError and a serial the library will not
    # accept raises ValueError
    except (LifxError, OSError, ValueError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host},
        ) from err
    entry.async_on_unload(device.close)

    coordinator = LIFXUpdateCoordinator(hass, entry, device)
    await coordinator.async_config_entry_first_refresh()
    async_repair_device_registry(hass, entry, coordinator.data)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, NUMBER_PLATFORM)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        # A failed setup only runs the unload callbacks, so the platform that
        # was forwarded on its own has to be taken back down here
        await hass.config_entries.async_unload_platforms(entry, NUMBER_PLATFORM)
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LIFXConfigEntry) -> bool:
    """Unload a config entry."""
    manager = hass.data[DATA_LIFX_MANAGER]
    try:
        # The device is about to be closed out from under any running effect
        await manager.async_stop_effects(entry.runtime_data.device)
    except LifxError as err:
        # Restoring the pre-effect state is best effort: an unreachable device
        # is the usual reason an entry is being unloaded in the first place
        LOGGER.debug("Could not stop the effects running on %s: %s", entry.title, err)
    return await hass.config_entries.async_unload_platforms(
        entry, [*NUMBER_PLATFORM, *PLATFORMS]
    )
