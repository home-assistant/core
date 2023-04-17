"""The Matter integration."""
from __future__ import annotations

import asyncio

import async_timeout
from matter_server.client import MatterClient
from matter_server.client.exceptions import (
    CannotConnect,
    FailedCommand,
    InvalidServerVersion,
)
from matter_server.common.models.error import MatterError
import voluptuous as vol

from homeassistant.components.hassio import AddonError, AddonManager, AddonState
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.service import async_register_admin_service

from .adapter import MatterAdapter
from .addon import get_addon_manager
from .api import async_register_api
from .const import CONF_INTEGRATION_CREATED_ADDON, CONF_USE_ADDON, DOMAIN, LOGGER
from .device_platform import DEVICE_PLATFORM
from .helpers import MatterEntryData, get_matter

CONNECT_TIMEOUT = 10
LISTEN_READY_TIMEOUT = 30


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Matter from a config entry."""
    if use_addon := entry.data.get(CONF_USE_ADDON):
        await _async_ensure_addon_running(hass, entry)

    matter_client = MatterClient(entry.data[CONF_URL], async_get_clientsession(hass))
    try:
        async with async_timeout.timeout(CONNECT_TIMEOUT):
            await matter_client.connect()
    except (CannotConnect, asyncio.TimeoutError) as err:
        raise ConfigEntryNotReady("Failed to connect to matter server") from err
    except InvalidServerVersion as err:
        if use_addon:
            addon_manager = _get_addon_manager(hass)
            addon_manager.async_schedule_update_addon(catch_error=True)
        else:
            async_create_issue(
                hass,
                DOMAIN,
                "invalid_server_version",
                is_fixable=False,
                severity=IssueSeverity.ERROR,
                translation_key="invalid_server_version",
            )
        raise ConfigEntryNotReady(f"Invalid server version: {err}") from err

    except Exception as err:
        LOGGER.exception("Failed to connect to matter server")
        raise ConfigEntryNotReady(
            "Unknown error connecting to the Matter server"
        ) from err

    async_delete_issue(hass, DOMAIN, "invalid_server_version")

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
        async with async_timeout.timeout(LISTEN_READY_TIMEOUT):
            await init_ready.wait()
    except asyncio.TimeoutError as err:
        listen_task.cancel()
        raise ConfigEntryNotReady("Matter client not ready") from err

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        _async_init_services(hass)

    # create an intermediate layer (adapter) which keeps track of the nodes
    # and discovery of platform entities from the node attributes
    matter = MatterAdapter(hass, matter_client, entry)
    hass.data[DOMAIN][entry.entry_id] = MatterEntryData(matter, listen_task)

    await hass.config_entries.async_forward_entry_setups(entry, DEVICE_PLATFORM)
    await matter.setup_nodes()

    # If the listen task is already failed, we need to raise ConfigEntryNotReady
    if listen_task.done() and (listen_error := listen_task.exception()) is not None:
        await hass.config_entries.async_unload_platforms(entry, DEVICE_PLATFORM)
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
    except Exception as err:  # pylint: disable=broad-except
        # We need to guard against unknown exceptions to not crash this task.
        LOGGER.exception("Unexpected exception: %s", err)
        if entry.state != ConfigEntryState.LOADED:
            raise

    if not hass.is_stopping:
        LOGGER.debug("Disconnected from server. Reloading integration")
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, DEVICE_PLATFORM)

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


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    unique_id = None

    for ident in device_entry.identifiers:
        if ident[0] == DOMAIN:
            unique_id = ident[1]
            break

    if not unique_id:
        return True

    matter_entry_data: MatterEntryData = hass.data[DOMAIN][config_entry.entry_id]
    matter_client = matter_entry_data.adapter.matter_client

    for node in await matter_client.get_nodes():
        if node.unique_id == unique_id:
            await matter_client.remove_node(node.node_id)
            break

    return True


@callback
def _async_init_services(hass: HomeAssistant) -> None:
    """Init services."""

    async def _node_id_from_ha_device_id(ha_device_id: str) -> int | None:
        """Get node id from ha device id."""
        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(ha_device_id)

        if device is None:
            return None

        matter_id = next(
            (
                identifier
                for identifier in device.identifiers
                if identifier[0] == DOMAIN
            ),
            None,
        )

        if not matter_id:
            return None

        unique_id = matter_id[1]

        matter_client = get_matter(hass).matter_client

        # This could be more efficient
        for node in await matter_client.get_nodes():
            if node.unique_id == unique_id:
                return node.node_id

        return None

    async def open_commissioning_window(call: ServiceCall) -> None:
        """Open commissioning window on specific node."""
        node_id = await _node_id_from_ha_device_id(call.data["device_id"])

        if node_id is None:
            raise HomeAssistantError("This is not a Matter device")

        matter_client = get_matter(hass).matter_client

        # We are sending device ID .

        try:
            await matter_client.open_commissioning_window(node_id)
        except FailedCommand as err:
            raise HomeAssistantError(str(err)) from err

    async_register_admin_service(
        hass,
        DOMAIN,
        "open_commissioning_window",
        open_commissioning_window,
        vol.Schema({"device_id": str}),
    )


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
