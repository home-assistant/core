"""Config flow for izone."""

import asyncio
from collections.abc import Iterable
from contextlib import suppress
import logging
import socket
from typing import Any

import pizone
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DATA_DISCOVERY_SERVICE, IZONE, TIMEOUT_DISCOVERY

_LOGGER = logging.getLogger(__name__)
HOMEKIT_DISCOVERY_LOCK_ID = f"{IZONE}_homekit_discovery"
SOURCE_IZONE_RESOLVED = "izone_resolved"


class _ControllerDiscoveryListener(pizone.Listener):
    """Temporary listener used during on-demand config flow discovery."""

    def __init__(
        self, controller_ready: asyncio.Event, target_ip: str | None = None
    ) -> None:
        self._controller_ready = controller_ready
        self._target_ip = target_ip
        self.controllers: dict[str, pizone.Controller] = {}

    @callback
    def controller_discovered(self, ctrl: pizone.Controller) -> None:
        self.controllers[ctrl.device_uid] = ctrl
        if self._target_ip is None or ctrl.device_ip == self._target_ip:
            self._controller_ready.set()


async def _async_resolve_host(host: str) -> str | None:
    """Resolve a host or IP to an IPv4 address string."""
    try:
        addr_info = await asyncio.get_running_loop().getaddrinfo(
            host, None, family=socket.AF_INET, type=socket.SOCK_STREAM
        )
    except OSError:
        return None

    if not addr_info:
        return None

    return addr_info[0][4][0]


async def _async_discover_controllers(
    hass: HomeAssistant,
    host: str | None = None,
) -> dict[str, pizone.Controller]:
    """Discover iZone controllers via broadcast using a temporary service."""
    target_ip = await _async_resolve_host(host) if host else None
    if host and target_ip is None:
        return {}

    if disco := hass.data.get(DATA_DISCOVERY_SERVICE):
        controllers = dict(disco.pi_disco.controllers)
        if target_ip is None:
            return controllers

        matched = {
            uid: controller
            for uid, controller in controllers.items()
            if controller.device_ip == target_ip
        }
        if matched:
            return matched

        controller_ready = asyncio.Event()
        listener = _ControllerDiscoveryListener(controller_ready, target_ip)
        disco.pi_disco.add_listener(listener)
        try:
            await disco.pi_disco.rescan()
            with suppress(TimeoutError):
                async with asyncio.timeout(TIMEOUT_DISCOVERY):
                    await controller_ready.wait()
        finally:
            disco.pi_disco.remove_listener(listener)

        return {
            uid: controller
            for uid, controller in listener.controllers.items()
            if controller.device_ip == target_ip
        }

    controller_ready = asyncio.Event()
    listener = _ControllerDiscoveryListener(controller_ready, target_ip)
    session = aiohttp_client.async_get_clientsession(hass)
    discovery = pizone.discovery(listener, session=session)

    # Start discovery and wait for a controller to be found or timeout. Close service
    # after it's found or timeout to clean up resources, we don't want it running in
    # the background if the user isn't setting up an integration
    try:
        await discovery.start_discovery()
        with suppress(TimeoutError):
            async with asyncio.timeout(TIMEOUT_DISCOVERY):
                await controller_ready.wait()
    finally:
        await discovery.close()

    if target_ip is None:
        return listener.controllers

    return {
        uid: controller
        for uid, controller in listener.controllers.items()
        if controller.device_ip == target_ip
    }


async def _async_get_controller_uid(hass: HomeAssistant, host: str) -> str | None:
    """Get controller UID for a host via the pizone discovery layer."""
    controllers = await _async_discover_controllers(hass, host)
    if not controllers:
        return None

    return next(iter(controllers.values())).device_uid


class IZoneConfigFlow(ConfigFlow, domain=IZONE):
    """Handle iZone config flow."""

    VERSION = 2
    _discovered_host: str | None = None
    _discovered_controller_uid: str | None = None
    _user_discovered_controllers: dict[str, pizone.Controller] | None = None

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        return await self.async_step_user(import_data or {})

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated setup."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema({vol.Optional(CONF_HOST): str})
            )
        host = user_input.get(CONF_HOST)
        if host:
            if not (uid := await _async_get_controller_uid(self.hass, host)):
                errors: dict[str, str] = {}
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({vol.Optional(CONF_HOST): str}),
                    errors=errors,
                )
            await self.async_set_unique_id(uid)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
            return self.async_create_entry(title=f"iZone {uid}", data={CONF_HOST: host})

        # Shared UDP discovery should only be driven by one active iZone flow.
        if self._async_in_progress(include_uninitialized=True):
            return self.async_abort(reason="already_in_progress")

        controllers = await _async_discover_controllers(self.hass)
        if not controllers:
            _LOGGER.debug("No controllers found")
            return self.async_abort(reason="no_devices_found")

        self._user_discovered_controllers = self._async_get_unconfigured_controllers(
            controllers
        )
        if not self._user_discovered_controllers:
            return self.async_abort(reason="already_configured")
        if len(self._user_discovered_controllers) > 1:
            return await self.async_step_select_controller()

        return await self._async_create_controller_entry(
            next(iter(self._user_discovered_controllers.values()))
        )

    async def async_step_select_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a controller when multiple unconfigured controllers are discovered."""
        if not self._user_discovered_controllers:
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            controller = self._user_discovered_controllers.get(user_input[CONF_HOST])
            if controller is None:
                return self.async_abort(reason="no_devices_found")

            # Fan out additional config flows for other discovered controllers so
            # they are surfaced in discovered devices without requiring another scan.
            self._async_fan_out_discovered_controllers(
                self._user_discovered_controllers.values(),
                selected_uid=controller.device_uid,
            )

            return await self._async_create_controller_entry(controller)

        sorted_controllers = sorted(
            self._user_discovered_controllers.items(),
            key=lambda item: (item[1].device_uid, item[0]),
        )

        return self.async_show_form(
            step_id="select_controller",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): vol.In(
                        {
                            host: f"{controller.device_uid} ({host})"
                            for host, controller in sorted_controllers
                        }
                    )
                }
            ),
        )

    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle HomeKit discovery."""
        self._discovered_host = None

        # HomeKit discovery is used as a trigger and UID source only.
        # Controller connectivity details come from iZone discovery.
        model = discovery_info.properties.get("md", "")
        if not model.startswith("iZone "):
            return self.async_abort(reason="no_devices_found")

        self._discovered_controller_uid = model.split(" ", 1)[1]

        # Can abort early without any network activity if the discovered HomeKit UID is already configured by another flow.
        if self.hass.config_entries.async_entry_for_domain_unique_id(
            IZONE, self._discovered_controller_uid
        ):
            return self.async_abort(reason="already_configured")

        # Hold a temporary lock while resolving HomeKit discovery through iZone
        # discovery so additional HomeKit packets do not start competing flows.
        await self.async_set_unique_id(HOMEKIT_DISCOVERY_LOCK_ID)

        controllers = await _async_discover_controllers(self.hass)
        if controller := controllers.get(self._discovered_controller_uid):
            self._discovered_host = controller.device_ip

        # Fan out additional config flows for other discovered controllers so
        # they are surfaced in discovered devices without requiring another scan.
        self._async_fan_out_discovered_controllers(
            controllers.values(),
            selected_uid=self._discovered_controller_uid,
        )

        # Restore the discovered UID after using the temporary lock ID.
        await self.async_set_unique_id(self._discovered_controller_uid)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": model}

        return await self.async_step_confirm()

    async def async_step_izone_resolved(
        self, resolved_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle internally resolved controller fan-out flows."""
        uid = resolved_info.get("uid")
        host = resolved_info.get("host")
        if not isinstance(uid, str) or not isinstance(host, str):
            return self.async_abort(reason="no_devices_found")

        self._discovered_controller_uid = uid
        self._discovered_host = host
        await self.async_set_unique_id(uid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self.context["title_placeholders"] = {"name": f"iZone {uid}"}
        return await self.async_step_confirm()

    @callback
    def _async_get_unconfigured_controllers(
        self, controllers: dict[str, pizone.Controller]
    ) -> dict[str, pizone.Controller]:
        """Return discovered controllers that do not already have config entries."""
        configured_uids = self._async_current_ids(include_ignore=False)
        return {
            controller.device_ip: controller
            for controller in controllers.values()
            if controller.device_uid not in configured_uids
        }

    async def _async_create_controller_entry(
        self, controller: pizone.Controller
    ) -> ConfigFlowResult:
        """Create a config entry for a discovered controller."""
        await self.async_set_unique_id(controller.device_uid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: controller.device_ip})
        return self.async_create_entry(
            title=f"iZone {controller.device_uid}",
            data={CONF_HOST: controller.device_ip},
        )

    @callback
    def _async_fan_out_discovered_controllers(
        self,
        controllers: Iterable[pizone.Controller],
        *,
        selected_uid: str,
    ) -> None:
        """Start resolved flows for discovered controllers except the selected UID."""
        current_ids = self._async_current_ids()
        in_progress_ids = {
            flow["context"].get("unique_id")
            for flow in self._async_in_progress(include_uninitialized=True)
        }
        for candidate in controllers:
            if candidate.device_uid == selected_uid:
                continue
            if (
                candidate.device_uid in current_ids
                or candidate.device_uid in in_progress_ids
            ):
                continue
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    IZONE,
                    context={"source": SOURCE_IZONE_RESOLVED},
                    data={
                        "uid": candidate.device_uid,
                        "host": candidate.device_ip,
                    },
                )
            )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup for discovery-driven flows."""
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    "controller_uid": self._discovered_controller_uid or "unknown",
                    "host": self._discovered_host or "unknown",
                },
            )

        if self._discovered_host:
            # Fast path when iZone discovery already resolved the HomeKit UID.
            uid = self._discovered_controller_uid
            if uid is not None:
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: self._discovered_host}
                )
                return self.async_create_entry(
                    title=f"iZone {uid}", data={CONF_HOST: self._discovered_host}
                )

        controllers = await _async_discover_controllers(self.hass)
        if controllers:
            if self._discovered_controller_uid:
                controller = controllers.get(self._discovered_controller_uid)
                if controller is None:
                    _LOGGER.debug(
                        "Discovered controller UID %s was not found during confirmation",
                        self._discovered_controller_uid,
                    )
                    return self.async_abort(reason="no_devices_found")
            else:
                controller = next(iter(controllers.values()))
            return await self._async_create_controller_entry(controller)

        _LOGGER.debug("No controllers found")
        return self.async_abort(reason="no_devices_found")
