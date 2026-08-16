"""The JFL Alarm integration.

One config entry is one listener; one subentry is one panel. Panels dial in to a single TCP port, so
a listener per panel would mean a port per panel.

The listener starts before the platforms are forwarded, so a panel that dials in during setup is
already being heard, and it stops after they are unloaded, so the port is genuinely freed.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pyjfl import JflServer

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    CONF_READ_ONLY,
    CONF_SERIAL,
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
)
from .coordinator import JflPanelCoordinator
from .device import build_panel_device

if TYPE_CHECKING:
    from collections.abc import Callable

    from pyjfl import ConnectionInfo

    from homeassistant.helpers.device_registry import DeviceEntry


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


async def async_setup_entry(hass: HomeAssistant, entry: JflConfigEntry) -> bool:
    """Start the listener and bring up one coordinator per configured panel."""
    server = JflServer(
        host=entry.data.get(CONF_HOST, DEFAULT_HOST),
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        keepalive_minutes=DEFAULT_KEEPALIVE_MINUTES,
        log_raw_frames=DEFAULT_LOG_RAW_FRAMES,
        unknown_panels=DEFAULT_UNKNOWN_PANELS,
    )

    try:
        await server.async_start()
    except OSError as err:
        # Almost always "address already in use". Retrying is right: whatever holds it may let go.
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
        # Registered before any entity so that a partition entity's `parent_device_id` lookup
        # always finds the panel. `async_refresh_panel_device` fills in the real model and firmware
        # once the panel dials in.
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
            programming_read_interval=DEFAULT_PROGRAMMING_READ_INTERVAL,
            read_only=subentry.data.get(CONF_READ_ONLY, DEFAULT_READ_ONLY),
        )
        await coordinator.async_setup_panel()
        runtime.coordinators[serial] = coordinator

    server.async_set_known_panels(set(runtime.coordinators))
    server.async_set_discovery_callback(_make_discovery_handler(hass, entry))

    _async_release_entities_of_enabled_devices(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
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
    """Allow deleting the device of a panel that no longer has a subentry."""
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
    """Re-enable entities marked disabled because of a device that is not disabled.

    Home Assistant clears `disabled_by: device` only through the device registry own update path, so
    a route that leaves the device row enabled without firing that update strands the entities with
    no way for the user to switch them back on.
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

    Adding the subentry updates the entry, which reloads it, which is what creates the coordinator
    and the entities.
    """

    @callback
    def _discovered(info: ConnectionInfo) -> None:
        if any(
            subentry.unique_id == info.serial for subentry in entry.subentries.values()
        ):  # pragma: no cover - the listener filters these out first
            return
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

    return _discovered
