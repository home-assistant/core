"""Config flow for izone."""

import asyncio
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
    await discovery.start_discovery()
    try:
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

    VERSION = 1
    _discovered_host: str | None = None
    _discovered_controller_uid: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input.get(CONF_HOST)
            if host:
                if not (uid := await _async_get_controller_uid(self.hass, host)):
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(uid)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                    return self.async_create_entry(
                        title=f"iZone {uid}", data={CONF_HOST: host}
                    )
            else:
                controllers = await _async_discover_controllers(self.hass)
                if not controllers:
                    _LOGGER.debug("No controllers found")
                    return self.async_abort(reason="no_devices_found")

                controller = next(iter(controllers.values()))
                await self.async_set_unique_id(controller.device_uid)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: controller.device_ip}
                )
                return self.async_create_entry(
                    title=f"iZone {controller.device_uid}",
                    data={CONF_HOST: controller.device_ip},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle HomeKit discovery."""
        host = getattr(discovery_info, "host", None)
        if host is None and isinstance(discovery_info, dict):
            host = discovery_info.get("host")
        self._discovered_host = None

        # Extract UID from HomeKit discovery model in properties (format: "iZone 000025841")
        properties = getattr(discovery_info, "properties", None)
        if properties is None and isinstance(discovery_info, dict):
            properties = discovery_info.get("properties", {})
        properties = properties or {}
        model = properties.get("md", "")
        if isinstance(model, str) and model.startswith("iZone "):
            self._discovered_controller_uid = model.split(" ", 1)[1]
            await self.async_set_unique_id(self._discovered_controller_uid)

            controllers = await _async_discover_controllers(self.hass)
            if controller := controllers.get(self._discovered_controller_uid):
                self._discovered_host = controller.device_ip
            elif (
                host
                and await _async_get_controller_uid(self.hass, host)
                == self._discovered_controller_uid
            ):
                self._discovered_host = host

            self._abort_if_unique_id_configured(
                updates={CONF_HOST: self._discovered_host or host}
            )
            self.context["title_placeholders"] = {"name": model}
        else:
            self._discovered_host = host

        return await self.async_step_confirm()

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
            # Use already-discovered UID if available, otherwise query device
            uid = self._discovered_controller_uid or await _async_get_controller_uid(
                self.hass, self._discovered_host
            )
            if uid:
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: self._discovered_host}
                )
                return self.async_create_entry(
                    title=f"iZone {uid}", data={CONF_HOST: self._discovered_host}
                )

        controllers = await _async_discover_controllers(self.hass)
        if controllers:
            controller = (
                controllers[self._discovered_controller_uid]
                if self._discovered_controller_uid
                and self._discovered_controller_uid in controllers
                else next(iter(controllers.values()))
            )
            await self.async_set_unique_id(controller.device_uid)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: controller.device_ip}
            )
            return self.async_create_entry(
                title=f"iZone {controller.device_uid}",
                data={CONF_HOST: controller.device_ip},
            )

        _LOGGER.debug("No controllers found")
        return self.async_abort(reason="no_devices_found")
