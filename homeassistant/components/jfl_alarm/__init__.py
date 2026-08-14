"""The JFL Alarm integration.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

One config entry is one **listener**; one subentry is one **panel**. That split follows the
protocol rather than convenience: panels dial in to a single TCP port, so a listener per panel would
mean a port per panel, and an installation with five panels would need five ports opened and five
reporting destinations that all differ.

Ordering matters at both ends of the lifecycle. The listener starts *before* the platforms are
forwarded, so a panel that dials in during setup is already being heard; and it stops *after* they
are unloaded, so nothing is still holding the socket when the port is meant to be free.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pyjfl import JflServer

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    CONF_KEEPALIVE_MINUTES,
    CONF_LOG_RAW_FRAMES,
    CONF_PROGRAMMING_READ_INTERVAL,
    CONF_READ_ONLY,
    CONF_SERIAL,
    CONF_UNKNOWN_PANELS,
    DEFAULT_HOST,
    DEFAULT_KEEPALIVE_MINUTES,
    DEFAULT_LOG_RAW_FRAMES,
    DEFAULT_PORT,
    DEFAULT_PROGRAMMING_READ_INTERVAL,
    DEFAULT_READ_ONLY,
    DEFAULT_STATUS_INTERVAL,
    DEFAULT_UNKNOWN_PANELS,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_PANEL,
    UNKNOWN_ACCEPT,
)
from .coordinator import JflPanelCoordinator
from .device import build_panel_device
from .repairs import async_watch_for_silence
from .services import async_register_services

if TYPE_CHECKING:
    from collections.abc import Callable

    from pyjfl import ConnectionInfo

    from homeassistant.helpers.device_registry import DeviceEntry
    from homeassistant.helpers.typing import ConfigType


@dataclass
class JflRuntimeData:
    """Everything one loaded config entry owns. Reached through `entry.runtime_data`."""

    server: JflServer
    coordinators: dict[str, JflPanelCoordinator] = field(default_factory=dict)
    """Keyed by panel serial, one per panel subentry."""


type JflConfigEntry = ConfigEntry[JflRuntimeData]

PLATFORMS: Final[list[Platform]] = [
    Platform.ALARM_CONTROL_PANEL,
]
"""Lives here rather than in `const.py` so that `const.py` needs no Home Assistant import: the test
asserting `DEFAULT_READ_ONLY is True` has to be runnable on a machine without it."""

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
"""No `configuration.yaml` path exists — see the module docstring. `async_setup` below only
registers the actions; it never reads *config*."""


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services.

    **Here and not in `async_setup_entry`** — AGENTS.md §5. A service registered per entry vanishes
    when that entry is unloaded, and an automation referring to it then fails validation for a
    reason that has nothing to do with the automation.
    """
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: JflConfigEntry) -> bool:
    """Start the listener and bring up one coordinator per configured panel."""
    options = entry.options
    server = JflServer(
        host=entry.data.get(CONF_HOST, DEFAULT_HOST),
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        keepalive_minutes=options.get(
            CONF_KEEPALIVE_MINUTES, DEFAULT_KEEPALIVE_MINUTES
        ),
        log_raw_frames=options.get(CONF_LOG_RAW_FRAMES, DEFAULT_LOG_RAW_FRAMES),
        unknown_panels=options.get(CONF_UNKNOWN_PANELS, DEFAULT_UNKNOWN_PANELS),
    )

    try:
        await server.async_start()
    except OSError as err:
        # Almost always "address already in use" — another Home Assistant, another integration, or
        # the old jfl_active integration still holding the port. Retrying is right: whatever holds
        # it may well let go.
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_bind",
            translation_placeholders={
                "host": server.host,
                "port": str(server.port),
                "error": str(err),
            },
        ) from err

    runtime = JflRuntimeData(server=server)
    entry.runtime_data = runtime

    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PANEL:
            continue
        serial = str(subentry.data[CONF_SERIAL])
        # Registered explicitly, and before any entity, so a partition/zone/fence entity's
        # `parent_device_id` lookup always finds the panel — building a child `DeviceInfo` no
        # longer accepts a bare `(DOMAIN, identifier)` pair, unlike the removed `via_device`.
        # `info=None` here is exactly the pre-connection fallback `build_panel_device` already
        # returns; `async_refresh_panel_device` overwrites it once the panel actually dials in.
        dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=subentry.subentry_id,
            **build_panel_device(None, serial, subentry.title),
        )
        coordinator = JflPanelCoordinator(
            hass,
            entry,
            subentry,
            server.link(serial),
            status_interval=DEFAULT_STATUS_INTERVAL,
            programming_read_interval=options.get(
                CONF_PROGRAMMING_READ_INTERVAL, DEFAULT_PROGRAMMING_READ_INTERVAL
            ),
            read_only=subentry.data.get(CONF_READ_ONLY, DEFAULT_READ_ONLY),
        )
        await coordinator.async_setup_panel()
        runtime.coordinators[serial] = coordinator

    server.async_set_known_panels(set(runtime.coordinators))
    server.async_set_discovery_callback(_make_discovery_handler(hass, entry))

    _async_release_entities_of_enabled_devices(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    async_watch_for_silence(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: JflConfigEntry) -> bool:
    """Unload the platforms, then stop the listener so the port is genuinely freed."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    runtime = entry.runtime_data
    for coordinator in runtime.coordinators.values():
        await coordinator.async_shutdown_panel()
    runtime.server.async_set_discovery_callback(None)
    await runtime.server.async_stop()
    return unloaded


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: JflConfigEntry, device: DeviceEntry
) -> bool:
    """Allow deleting the device of a panel that no longer has a subentry.

    A panel that was replaced leaves behind a device that will never update again, and without this
    the user has no way to get rid of it.
    """
    live = set(entry.runtime_data.coordinators)
    owned = {
        identifier[1].split("-", 1)[0]
        for identifier in device.identifiers
        if identifier[0] == DOMAIN
    }
    return not owned & live


@callback
def _async_release_entities_of_enabled_devices(
    hass: HomeAssistant, entry: JflConfigEntry
) -> None:
    """Re-enable entities left marked "disabled because their device is", on a device that is not.

    **This is a dead end the user cannot get out of.** Home Assistant writes `disabled_by: device`
    on every entity of a device it disables, and clears it again when that device is re-enabled —
    but only through the device registry's own update path. A config entry disabled and then
    re-enabled by editing `.storage` by hand (which is how the lab's entry was brought back on
    2026-08-09), or any other route that leaves the device row enabled without firing that update,
    strands the entities: the frontend refuses to enable one whose device it believes is disabled,
    and the device it names is enabled, so there is nothing to switch. The author hit exactly this
    on a partition's `alarm_control_panel` entity, which was unreachable until this function was
    added.

    Nothing in this integration writes those flags, so this cannot un-do a deliberate choice: a
    device the user really has disabled is skipped, and an entity the user disabled themselves is
    marked `disabled_by: user` and is skipped too. It runs before the platforms are forwarded, so a
    released entity is added in the same setup rather than after another restart.
    """
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    for entity in er.async_entries_for_config_entry(entities, entry.entry_id):
        if entity.disabled_by is not er.RegistryEntryDisabler.DEVICE:
            continue
        device = devices.async_get(entity.device_id) if entity.device_id else None
        if device is None or device.disabled:
            continue
        LOGGER.debug(
            "re-enabling %s: it is disabled because of a device that is not disabled",
            entity.entity_id,
        )
        entities.async_update_entity(entity.entity_id, disabled_by=None)


async def _async_update_listener(hass: HomeAssistant, entry: JflConfigEntry) -> None:
    """Reload when options or subentries change; both are read only at setup time."""
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _make_discovery_handler(
    hass: HomeAssistant, entry: JflConfigEntry
) -> Callable[[ConnectionInfo], None]:
    """Return the callback that turns an unconfigured panel into a subentry.

    Registered only so that the *accept* policy has somewhere to send a discovery; the listener
    itself decides whether to call it. Adding the subentry updates the entry, which reloads it,
    which is what actually creates the coordinator and the entities.
    """

    @callback
    def _discovered(info: ConnectionInfo) -> None:
        if any(
            subentry.unique_id == info.serial for subentry in entry.subentries.values()
        ):  # pragma: no cover - the listener filters these out first
            return
        # Once per panel per Home Assistant restart, and it is the answer to "why has nothing
        # appeared?". That is exactly what AGENTS.md §4 reserves `info` for.
        LOGGER.info(
            "New JFL panel %s (%s) reported in and was added automatically",
            info.serial,
            info.spec.name,
        )
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(
                    {CONF_SERIAL: info.serial, CONF_READ_ONLY: DEFAULT_READ_ONLY}
                ),
                subentry_type=SUBENTRY_TYPE_PANEL,
                title=f"{info.spec.name} {info.serial}",
                unique_id=info.serial,
            ),
        )

    if entry.options.get(CONF_UNKNOWN_PANELS, DEFAULT_UNKNOWN_PANELS) != UNKNOWN_ACCEPT:
        return _ignore_discovery
    return _discovered


@callback
def _ignore_discovery(info: ConnectionInfo) -> None:
    """Do nothing with a discovered panel. Used when the policy is *hold* or *reject*."""
    LOGGER.debug("panel %s reported in but is not configured", info.serial)
