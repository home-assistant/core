"""The Matter integration."""

from __future__ import annotations

import asyncio
from functools import cache

from matter_server.client import MatterClient
from matter_server.client.exceptions import (
    CannotConnect,
    InvalidServerVersion,
    NotConnected,
    ServerVersionTooNew,
    ServerVersionTooOld,
)
from matter_server.common.errors import MatterError, NodeNotExists

from homeassistant.components.hassio import AddonError, AddonManager, AddonState
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .adapter import MatterAdapter
from .addon import get_addon_manager
from .api import async_register_api
from .const import CONF_INTEGRATION_CREATED_ADDON, CONF_USE_ADDON, DOMAIN, LOGGER
from .discovery import SUPPORTED_PLATFORMS
from .helpers import (
    MatterEntryData,
    get_matter,
    get_node_from_device_entry,
    node_from_ha_device_id,
)
from .models import MatterDeviceInfo

CONNECT_TIMEOUT = 10
LISTEN_READY_TIMEOUT = 30


@callback
@cache
def get_matter_device_info(
    hass: HomeAssistant, device_id: str
) -> MatterDeviceInfo | None:
    """Return Matter device info or None if device does not exist."""
    # Test hass.data[DOMAIN] to ensure config entry is set up
    if not hass.data.get(DOMAIN, False) or not (
        node := node_from_ha_device_id(hass, device_id)
    ):
        return None

    return MatterDeviceInfo(
        unique_id=node.device_info.uniqueID,
        vendor_id=hex(node.device_info.vendorID),
        product_id=hex(node.device_info.productID),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Matter from a config entry."""
    if use_addon := entry.data.get(CONF_USE_ADDON):
        await _async_ensure_addon_running(hass, entry)

    matter_client = MatterClient(entry.data[CONF_URL], async_get_clientsession(hass))
    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            await matter_client.connect()
    except (CannotConnect, TimeoutError) as err:
        raise ConfigEntryNotReady("Failed to connect to matter server") from err
    except InvalidServerVersion as err:
        if isinstance(err, ServerVersionTooOld):
            if use_addon:
                addon_manager = _get_addon_manager(hass)
                addon_manager.async_schedule_update_addon(catch_error=True)
            else:
                async_create_issue(
                    hass,
                    DOMAIN,
                    "server_version_version_too_old",
                    is_fixable=False,
                    severity=IssueSeverity.ERROR,
                    translation_key="server_version_version_too_old",
                )
        elif isinstance(err, ServerVersionTooNew):
            async_create_issue(
                hass,
                DOMAIN,
                "server_version_version_too_new",
                is_fixable=False,
                severity=IssueSeverity.ERROR,
                translation_key="server_version_version_too_new",
            )
        raise ConfigEntryNotReady(f"Invalid server version: {err}") from err

    except Exception as err:
        LOGGER.exception("Failed to connect to matter server")
        raise ConfigEntryNotReady(
            "Unknown error connecting to the Matter server"
        ) from err

    async_delete_issue(hass, DOMAIN, "server_version_version_too_old")
    async_delete_issue(hass, DOMAIN, "server_version_version_too_new")

    async def on_hass_stop(event: Event) -> None:
        """Handle incoming stop event from Home Assistant."""
        await matter_client.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    async_register_api(hass)

    # launch the matter client listen task in the background
    # use the init_ready event to wait until initialization is done
    init_ready = asyncio.Event()
    listen_task = asyncio.create_task(
        _client_listen(hass, entry, matter_client, init_ready)
    )

    try:
        async with asyncio.timeout(LISTEN_READY_TIMEOUT):
            await init_ready.wait()
    except TimeoutError as err:
        listen_task.cancel()
        raise ConfigEntryNotReady("Matter client not ready") from err

    # Set default fabric
    try:
        await matter_client.set_default_fabric_label(
            hass.config.location_name or "Home"
        )
    except (NotConnected, MatterError) as err:
        listen_task.cancel()
        raise ConfigEntryNotReady("Failed to set default fabric label") from err

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # create an intermediate layer (adapter) which keeps track of the nodes
    # and discovery of platform entities from the node attributes
    matter = MatterAdapter(hass, matter_client, entry)
    hass.data[DOMAIN][entry.entry_id] = MatterEntryData(matter, listen_task)

    await hass.config_entries.async_forward_entry_setups(entry, SUPPORTED_PLATFORMS)
    await matter.setup_nodes()

    # If the listen task is already failed, we need to raise ConfigEntryNotReady
    if listen_task.done() and (listen_error := listen_task.exception()) is not None:
        await hass.config_entries.async_unload_platforms(entry, SUPPORTED_PLATFORMS)
        hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await matter_client.disconnect()
        finally:
            raise ConfigEntryNotReady(listen_error) from listen_error

    return True


async def _client_listen(
    hass: HomeAssistant,
    entry: ConfigEntry,
    matter_client: MatterClient,
    init_ready: asyncio.Event,
) -> None:
    """Listen with the client."""
    try:
        await matter_client.start_listening(init_ready)
    except MatterError as err:
        if entry.state != ConfigEntryState.LOADED:
            raise
        LOGGER.error("Failed to listen: %s", err)
    except Exception as err:  # noqa: BLE001
        # We need to guard against unknown exceptions to not crash this task.
        LOGGER.exception("Unexpected exception: %s", err)
        if entry.state != ConfigEntryState.LOADED:
            raise

    if not hass.is_stopping:
        LOGGER.debug("Disconnected from server. Reloading integration")
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, SUPPORTED_PLATFORMS
    )

    if unload_ok:
        matter_entry_data: MatterEntryData = hass.data[DOMAIN].pop(entry.entry_id)
        matter_entry_data.listen_task.cancel()
        await matter_entry_data.adapter.matter_client.disconnect()

    if entry.data.get(CONF_USE_ADDON) and entry.disabled_by:
        addon_manager: AddonManager = get_addon_manager(hass)
        LOGGER.debug("Stopping Matter Server add-on")
        try:
            await addon_manager.async_stop_addon()
        except AddonError as err:
            LOGGER.error("Failed to stop the Matter Server add-on: %s", err)
            return False

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Config entry is being removed."""

    if not entry.data.get(CONF_INTEGRATION_CREATED_ADDON):
        return

    addon_manager: AddonManager = get_addon_manager(hass)
    try:
        await addon_manager.async_stop_addon()
    except AddonError as err:
        LOGGER.error(err)
        return
    try:
        await addon_manager.async_create_backup()
    except AddonError as err:
        LOGGER.error(err)
        return
    try:
        await addon_manager.async_uninstall_addon()
    except AddonError as err:
        LOGGER.error(err)


def _remove_via_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> None:
    """Remove all via devices associated with a device."""
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    for device in devices:
        if device.via_device_id == device_entry.id:
            device_registry.async_update_device(
                device.id, remove_config_entry_id=config_entry.entry_id
            )


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    node = get_node_from_device_entry(hass, device_entry)

    if node is None:
        # In case this was a bridge
        _remove_via_devices(hass, config_entry, device_entry)
        # Always allow users to remove orphan devices
        return True

    if device_entry.via_device_id:
        # Do not allow to delete devices that exposed via bridge.
        return False

    matter = get_matter(hass)
    try:
        await matter.matter_client.remove_node(node.node_id)
    except NodeNotExists:
        # Ignore if the server has already removed the node.
        LOGGER.debug("Node %s didn't exist on the Matter server", node.node_id)
    finally:
        # Make sure potentially orphan devices of a bridge are removed too.
        if node.is_bridge_device:
            _remove_via_devices(hass, config_entry, device_entry)

    return True


async def _async_ensure_addon_running(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ensure that Matter Server add-on is installed and running."""
    addon_manager = _get_addon_manager(hass)
    try:
        addon_info = await addon_manager.async_get_addon_info()
    except AddonError as err:
        raise ConfigEntryNotReady(err) from err

    addon_state = addon_info.state

    if addon_state == AddonState.NOT_INSTALLED:
        addon_manager.async_schedule_install_setup_addon(
            addon_info.options,
            catch_error=True,
        )
        raise ConfigEntryNotReady

    if addon_state == AddonState.NOT_RUNNING:
        addon_manager.async_schedule_start_addon(catch_error=True)
        raise ConfigEntryNotReady


@callback
def _get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Ensure that Matter Server add-on is updated and running.

    May only be used as part of async_setup_entry above.
    """
    addon_manager: AddonManager = get_addon_manager(hass)
    if addon_manager.task_in_progress():
        raise ConfigEntryNotReady
    return addon_manager
