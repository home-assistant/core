"""The Matter integration."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

import async_timeout
from matter_server.client.exceptions import (
    CannotConnect,
    FailedCommand,
    InvalidServerVersion,
)
from matter_server.client.matter import Matter
import voluptuous as vol

from homeassistant.components.hassio import AddonError, AddonManager, AddonState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.service import async_register_admin_service

from .adapter import MatterAdapter, get_matter_store
from .addon import get_addon_manager
from .api import async_register_api
from .const import CONF_INTEGRATION_CREATED_ADDON, CONF_USE_ADDON, DOMAIN, LOGGER
from .device_platform import DEVICE_PLATFORM


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Matter from a config entry."""
    if use_addon := entry.data.get(CONF_USE_ADDON):
        await _async_ensure_addon_running(hass, entry)

    matter = Matter(MatterAdapter(hass, entry))
    try:
        await matter.connect()
    except CannotConnect as err:
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
        matter.adapter.logger.exception("Failed to connect to matter server")
        raise ConfigEntryNotReady(
            "Unknown error connecting to the Matter server"
        ) from err
    else:
        async_delete_issue(hass, DOMAIN, "invalid_server_version")

    async def on_hass_stop(event: Event) -> None:
        """Handle incoming stop event from Home Assistant."""
        await matter.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    async_register_api(hass)

    matter.listen()
    try:
        async with async_timeout.timeout(30):
            await matter.driver_ready.wait()
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady("Matter driver not ready") from err

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        _async_init_services(hass)

    hass.data[DOMAIN][entry.entry_id] = matter

    await hass.config_entries.async_forward_entry_setups(entry, DEVICE_PLATFORM)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, DEVICE_PLATFORM)

    if unload_ok:
        matter: Matter = hass.data[DOMAIN].pop(entry.entry_id)
        await matter.disconnect()

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
    # Remove storage file.
    storage_path = get_matter_store(hass, entry).path
    await hass.async_add_executor_job(Path(storage_path).unlink)

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

    matter: Matter = hass.data[DOMAIN][config_entry.entry_id]

    for node in matter.get_nodes():
        if node.unique_id == unique_id:
            await matter.delete_node(node.node_id)
            break

    return True


@callback
def _async_init_services(hass: HomeAssistant) -> None:
    """Init services."""

    async def commission(call: ServiceCall) -> None:
        """Handle commissioning."""
        matter: Matter = list(hass.data[DOMAIN].values())[0]
        try:
            await matter.commission(call.data["code"])
        except FailedCommand as err:
            raise HomeAssistantError(str(err)) from err

    async_register_admin_service(
        hass,
        DOMAIN,
        "commission",
        commission,
        vol.Schema({"code": str}),
    )

    async def accept_shared_device(call: ServiceCall) -> None:
        """Accept a shared device."""
        matter: Matter = list(hass.data[DOMAIN].values())[0]
        try:
            await matter.commission_on_network(call.data["pin"])
        except FailedCommand as err:
            raise HomeAssistantError(str(err)) from err

    async_register_admin_service(
        hass,
        DOMAIN,
        "accept_shared_device",
        accept_shared_device,
        vol.Schema({"pin": vol.Coerce(int)}),
    )

    async def set_wifi(call: ServiceCall) -> None:
        """Handle set wifi creds."""
        matter: Matter = list(hass.data[DOMAIN].values())[0]
        try:
            await matter.client.driver.device_controller.set_wifi_credentials(
                call.data["network_name"], call.data["password"]
            )
        except FailedCommand as err:
            raise HomeAssistantError(str(err)) from err

    async_register_admin_service(
        hass,
        DOMAIN,
        "set_wifi",
        set_wifi,
        vol.Schema(
            {
                "network_name": str,
                "password": str,
            }
        ),
    )

    async def set_thread(call: ServiceCall) -> None:
        """Handle set Thread creds."""
        matter: Matter = list(hass.data[DOMAIN].values())[0]
        thread_dataset = bytes.fromhex(call.data["thread_operation_dataset"])
        try:
            await matter.client.driver.device_controller.set_thread_operational_dataset(
                thread_dataset
            )
        except FailedCommand as err:
            raise HomeAssistantError(str(err)) from err

    async_register_admin_service(
        hass,
        DOMAIN,
        "set_thread",
        set_thread,
        vol.Schema({"thread_operation_dataset": str}),
    )

    @callback
    def _node_id_from_ha_device_id(ha_device_id: str) -> int | None:
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

        matter: Matter = next(iter(hass.data[DOMAIN].values()))

        # This could be more efficient
        for node in matter.get_nodes():
            if node.unique_id == unique_id:
                return cast(int, node.node_id)

        return None

    async def open_commissioning_window(call: ServiceCall) -> None:
        """Open commissioning window on specific node."""
        node_id = _node_id_from_ha_device_id(call.data["device_id"])

        if node_id is None:
            raise HomeAssistantError("This is not a Matter device")

        matter: Matter = list(hass.data[DOMAIN].values())[0]

        # We are sending device ID .

        try:
            await matter.client.driver.device_controller.open_commissioning_window(
                node_id
            )
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
