"""The Poolside integration."""

from base64 import b64decode
from collections.abc import Callable
from dataclasses import dataclass

from aiopoolside import (
    PoolsideAuthError,
    PoolsideClient,
    PoolsideCommandError,
    PoolsideConnectionError,
    PoolsideControl,
    PoolsideDevice,
    PoolsideSite,
)
from aiopoolside.const import LAST_TIME_SITE_WAS_LOADED_FIELD, ControlType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    CONF_CLIENT_PRIVATE_KEY,
    CONF_CONTROLLER_PUBLIC_KEY,
    CONF_CONTROLLER_UUID,
    CONF_EXPOSE_POOL_DEVICES,
    DEFAULT_EXPOSE_POOL_DEVICES,
    DOMAIN,
    LOGGER,
    SITE_MODE_KEY,
)
from .entity import control_platform

PLATFORMS = [
    Platform.CLIMATE,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class PoolsideData:
    """Runtime data for a Poolside config entry."""

    client: PoolsideClient
    site: PoolsideSite
    controls: list[PoolsideControl]
    pool_devices: list[PoolsideDevice]


type PoolsideConfigEntry = ConfigEntry[PoolsideData]


async def async_setup_entry(hass: HomeAssistant, entry: PoolsideConfigEntry) -> bool:
    """Set up Poolside from a config entry."""
    client = PoolsideClient(
        session=aiohttp_client.async_get_clientsession(hass),
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        client_private_key=b64decode(entry.data[CONF_CLIENT_PRIVATE_KEY]),
        controller_public_key=b64decode(entry.data[CONF_CONTROLLER_PUBLIC_KEY]),
        controller_uuid=entry.data[CONF_CONTROLLER_UUID],
    )

    try:
        await client.async_connect()
    except PoolsideAuthError as err:
        raise ConfigEntryAuthFailed from err
    except PoolsideConnectionError as err:
        raise ConfigEntryNotReady from err

    client.set_auth_failure_callback(lambda: entry.async_start_reauth(hass))

    try:
        site, controls = await client.async_get_control_layout()
    except (PoolsideConnectionError, PoolsideCommandError) as err:
        await client.async_disconnect()
        raise ConfigEntryNotReady from err

    pool_devices: list[PoolsideDevice] = []
    if entry.options.get(CONF_EXPOSE_POOL_DEVICES, DEFAULT_EXPOSE_POOL_DEVICES):
        try:
            pool_devices = await client.async_get_pool_devices()
        except PoolsideCommandError as err:
            # Expected on older controller firmware without Site.getPoolDevices,
            # but loud enough to catch a renamed/misrouted method during testing.
            LOGGER.warning(
                "Controller rejected Site.getPoolDevices; no pool devices will be"
                " created: %s",
                err,
            )
        except PoolsideConnectionError as err:
            await client.async_disconnect()
            raise ConfigEntryNotReady from err
        LOGGER.debug(
            "Loaded %d pool device(s): %s",
            len(pool_devices),
            [(device.uuid, device.name, device.device_type) for device in pool_devices],
        )

    entry.runtime_data = PoolsideData(
        client=client, site=site, controls=controls, pool_devices=pool_devices
    )

    _async_prune_stale_registry_entries(hass, entry, controls, pool_devices)
    _async_register_devices(hass, entry, client, site, pool_devices)

    if site.uuid is not None:
        entry.async_on_unload(_watch_for_site_reload(hass, entry, client, site.uuid))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


@callback
def _async_register_devices(
    hass: HomeAssistant,
    entry: PoolsideConfigEntry,
    client: PoolsideClient,
    site: PoolsideSite,
    pool_devices: list[PoolsideDevice],
) -> None:
    """Register the controller hub and its pool device sub-devices up front.

    Pool devices may carry no entities until their InformationFields state
    arrives, and via_device needs the hub to already exist, so both are
    created explicitly instead of as a side effect of entity setup.
    """
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, client.controller_uuid)},
        name=site.name,
        manufacturer="Poolside",
        model="Controller",
    )
    for device in pool_devices:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device.uuid)},
            via_device=(DOMAIN, client.controller_uuid),
            name=device.name,
            manufacturer="Poolside",
            model=device.device_type,
        )


@callback
def _async_prune_stale_registry_entries(
    hass: HomeAssistant,
    entry: PoolsideConfigEntry,
    controls: list[PoolsideControl],
    pool_devices: list[PoolsideDevice],
) -> None:
    """Remove registry entries that no longer match the control layout.

    The attendant can delete controls or whole groups; the resulting reload
    re-fetches the layout, and anything registered under a UUID that didn't
    come back would otherwise linger as a permanently-unavailable entity.
    A control that survives but is rendered on a different platform than
    before (e.g. a filter reconfigured from single- to variable-speed moves
    from switch to fan) similarly leaves its old-platform entity behind, so
    each UUID is checked against the entity domains it may legitimately
    have, not just for existence.

    Entity unique_ids are `{controller}_{uuid}` or `{controller}_{uuid}_{key}`
    where the UUID is a control's, a body of water's, or a pool device's; the
    site mode sensor (`{controller}_site_mode`) is the one exception. Group
    and pool devices are identified by their own UUID, the controller device
    by the controller UUID.
    """
    controller_uuid: str = entry.data[CONF_CONTROLLER_UUID]
    allowed_domains: dict[str, set[str]] = {}
    valid_identifiers: set[tuple[str, str]] = {(DOMAIN, controller_uuid)}
    for control in controls:
        domains = allowed_domains.setdefault(control.uuid, set())
        domains.add(control_platform(control).value)
        # Every control also carries diagnostic sensors (disabled reason).
        domains.add(Platform.SENSOR.value)
        if control.control_type is ControlType.TEMPERATURE:
            domains.add(Platform.SELECT.value)
        valid_identifiers.add((DOMAIN, control.group.uuid))
        if (body_of_water_uuid := control.group.body_of_water_uuid) is not None:
            allowed_domains.setdefault(body_of_water_uuid, set()).add(
                Platform.SENSOR.value
            )
    for device in pool_devices:
        allowed_domains.setdefault(device.uuid, set()).add(Platform.SENSOR.value)
        valid_identifiers.add((DOMAIN, device.uuid))

    entity_registry = er.async_get(hass)
    prefix = f"{controller_uuid}_"
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        remainder = entity_entry.unique_id.removeprefix(prefix)
        if remainder == SITE_MODE_KEY or any(
            (remainder == uuid or remainder.startswith(f"{uuid}_"))
            and entity_entry.domain in domains
            for uuid, domains in allowed_domains.items()
        ):
            continue
        LOGGER.debug(
            "Removing stale entity %s (unique_id %s)",
            entity_entry.entity_id,
            entity_entry.unique_id,
        )
        entity_registry.async_remove(entity_entry.entity_id)

    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if device_entry.identifiers & valid_identifiers:
            continue
        LOGGER.debug(
            "Removing stale device %s (%s)",
            device_entry.name,
            device_entry.identifiers,
        )
        device_registry.async_update_device(
            device_entry.id, remove_config_entry_id=entry.entry_id
        )


def _watch_for_site_reload(
    hass: HomeAssistant,
    entry: PoolsideConfigEntry,
    client: PoolsideClient,
    site_uuid: str,
) -> Callable[[], None]:
    """Reload the entry whenever the attendant's site configuration changes.

    `LastTimeSiteWasLoaded` changes whenever the attendant edits the site's
    configuration (adding/removing controls, bodies of water, ...) - the
    cached control layout is then stale and the entry needs a full reload to
    re-fetch it. The baseline is established from whatever value (including
    None) is already known when this is first called, so it never fires a
    reload just for having started up.
    """
    baseline = client.get_status(site_uuid, LAST_TIME_SITE_WAS_LOADED_FIELD)

    def on_status_change() -> None:
        nonlocal baseline
        current = client.get_status(site_uuid, LAST_TIME_SITE_WAS_LOADED_FIELD)
        if current == baseline:
            return
        LOGGER.debug(
            "Site %s configuration changed (%r -> %r); reloading",
            site_uuid,
            baseline,
            current,
        )
        baseline = current
        hass.config_entries.async_schedule_reload(entry.entry_id)

    return client.subscribe_status(site_uuid, on_status_change)


async def async_unload_entry(hass: HomeAssistant, entry: PoolsideConfigEntry) -> bool:
    """Unload a Poolside config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.async_disconnect()
    return unload_ok
