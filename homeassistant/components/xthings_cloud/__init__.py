"""Xthings Cloud integration for Home Assistant."""

from typing import Any

from ha_xthings_cloud import XthingsCloudApiClient, XthingsCloudApiError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from .const import CONF_REMOTE_ACCESS, DOMAIN, LOGGER, PLATFORMS
from .coordinator import XthingsCloudConfigEntry, XthingsCloudCoordinator
from .remote_access import async_disable_remote_access, async_enable_remote_access
from .sso import XthingsSsoManager, XthingsSsoView


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Xthings Cloud integration."""
    hass.http.register_view(XthingsSsoView)
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: XthingsCloudConfigEntry
) -> bool:
    """Set up config entry."""
    session = async_get_clientsession(hass)
    client = XthingsCloudApiClient(session, token=entry.data[CONF_TOKEN])
    hass.data.setdefault(DOMAIN, {})
    sso_manager = XthingsSsoManager(hass, entry, client)
    hass.data[DOMAIN]["sso"] = sso_manager
    coordinator = XthingsCloudCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start_websocket()

    if entry.options.get(CONF_REMOTE_ACCESS, False):
        await _async_bind_and_enable_remote_access(hass, client)

    remote_access_enabled = entry.options.get(CONF_REMOTE_ACCESS, False)
    unbind_requested = False

    async def _async_unbind_once() -> None:
        nonlocal unbind_requested
        if unbind_requested:
            return
        unbind_requested = True
        instance_id = await async_get_instance_id(hass)
        try:
            await client.async_unbind(instance_id)
        except (XthingsCloudApiError, TimeoutError):
            LOGGER.exception("Failed to unbind Home Assistant device")

    async def _async_device_registry_updated(event: Any) -> None:
        data = event.data
        if data["action"] != "update":
            return
        if "disabled_by" not in data["changes"]:
            return
        device = dr.async_get(hass).async_get_device(data["device_id"])
        if device is None or device.config_entry_id != entry.entry_id:
            return
        if data["changes"]["disabled_by"] is None:
            return
        await _async_unbind_once()

    entry.async_on_unload(
        hass.bus.async_listen(
            EVENT_DEVICE_REGISTRY_UPDATED, _async_device_registry_updated
        )
    )

    async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
        nonlocal remote_access_enabled
        enabled = entry.options.get(CONF_REMOTE_ACCESS, False)
        if enabled == remote_access_enabled:
            return
        remote_access_enabled = enabled
        await _async_options_updated(hass, entry)

    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: XthingsCloudConfigEntry
) -> bool:
    """Unload config entry."""
    coordinator = entry.runtime_data
    await async_disable_remote_access(hass)
    sso_manager = hass.data.get(DOMAIN, {}).pop("sso", None)
    if isinstance(sso_manager, XthingsSsoManager):
        await sso_manager.async_revoke_sessions()
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await coordinator.async_stop_websocket()
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: XthingsCloudConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Unbind the Home Assistant instance before removing its device."""
    if not any(identifier[0] == DOMAIN for identifier in device_entry.identifiers):
        return True
    session = async_get_clientsession(hass)
    client = XthingsCloudApiClient(session, token=entry.data[CONF_TOKEN])
    instance_id = await async_get_instance_id(hass)
    try:
        await client.async_unbind(instance_id)
    except (XthingsCloudApiError, TimeoutError):
        LOGGER.exception("Failed to unbind Home Assistant before device removal")
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply integration option changes."""
    session = async_get_clientsession(hass)
    client = XthingsCloudApiClient(session, token=entry.data[CONF_TOKEN])
    if entry.options.get(CONF_REMOTE_ACCESS, False):
        await _async_bind_and_enable_remote_access(hass, client)
    else:
        await async_disable_remote_access(hass)
        instance_id = await async_get_instance_id(hass)
        try:
            await client.async_unbind(instance_id)
        except (XthingsCloudApiError, TimeoutError):
            LOGGER.exception("FRP stopped, but failed to unbind Home Assistant")


async def _async_bind_and_enable_remote_access(
    hass: HomeAssistant, client: XthingsCloudApiClient
) -> None:
    """Bind this instance before enabling its remote tunnel."""
    instance_id = await async_get_instance_id(hass)
    try:
        owner = await hass.auth.async_get_owner()
        if owner is None:
            raise RuntimeError("Home Assistant owner is not available")
        await client.async_bind(
            instance_id,
            sso_ha_user_id=owner.id,
        )
    except (XthingsCloudApiError, TimeoutError):
        await async_disable_remote_access(hass)
        LOGGER.exception("Failed to bind Home Assistant; remote access is stopped")
        return
    await async_enable_remote_access(hass, client, instance_id)
