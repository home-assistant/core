"""Config flow for Matter integration."""

from __future__ import annotations

import asyncio
from typing import Any

from matter_server.client import MatterClient
from matter_server.client.exceptions import CannotConnect, InvalidServerVersion
import voluptuous as vol

from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
)
from homeassistant.components.onboarding import async_is_onboarded
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.hassio import is_hassio
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .addon import get_addon_manager
from .const import (
    ADDON_SLUG,
    CONF_INTEGRATION_CREATED_ADDON,
    CONF_USE_ADDON,
    DOMAIN,
    LOGGER,
)

ADDON_SETUP_TIMEOUT = 5
ADDON_SETUP_TIMEOUT_ROUNDS = 40
DEFAULT_URL = "ws://localhost:5580/ws"
DEFAULT_TITLE = "Matter"
ON_SUPERVISOR_SCHEMA = vol.Schema({vol.Optional(CONF_USE_ADDON, default=True): bool})


def get_manual_schema(user_input: dict[str, Any]) -> vol.Schema:
    """Return a schema for the manual step."""
    default_url = user_input.get(CONF_URL, DEFAULT_URL)
    return vol.Schema({vol.Required(CONF_URL, default=default_url): str})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    client = MatterClient(data[CONF_URL], aiohttp_client.async_get_clientsession(hass))
    await client.connect()


def build_ws_address(host: str, port: int) -> str:
    """Return the websocket address."""
    return f"ws://{host}:{port}/ws"


class MatterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Matter."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up flow instance."""
        self._running_in_background = False
        self.ws_address: str | None = None
        # If we install the add-on we should uninstall it on entry remove.
        self.integration_created_addon = False
        self.install_task: asyncio.Task | None = None
        self.start_task: asyncio.Task | None = None
        self.use_addon = False

    async def async_step_install_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Matter Server add-on."""
        if not self.install_task:
            self.install_task = self.hass.async_create_task(self._async_install_addon())

        if not self._running_in_background and not self.install_task.done():
            return self.async_show_progress(
                step_id="install_addon",
                progress_action="install_addon",
                progress_task=self.install_task,
            )

        try:
            await self.install_task
        except AddonError as err:
            LOGGER.error(err)
            if self._running_in_background:
                return await self.async_step_install_failed()
            return self.async_show_progress_done(next_step_id="install_failed")
        finally:
            self.install_task = None

        self.integration_created_addon = True

        if self._running_in_background:
            return await self.async_step_start_addon()
        return self.async_show_progress_done(next_step_id="start_addon")

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add-on installation failed."""
        return self.async_abort(reason="addon_install_failed")

    async def _async_install_addon(self) -> None:
        """Install the Matter Server add-on."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        await addon_manager.async_schedule_install_addon()

    async def _async_get_addon_discovery_info(self) -> dict:
        """Return add-on discovery info."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            discovery_info_config = await addon_manager.async_get_addon_discovery_info()
        except AddonError as err:
            LOGGER.error(err)
            raise AbortFlow("addon_get_discovery_info_failed") from err

        return discovery_info_config

    async def async_step_start_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start Matter Server add-on."""
        if not self.start_task:
            self.start_task = self.hass.async_create_task(self._async_start_addon())
        if not self._running_in_background and not self.start_task.done():
            return self.async_show_progress(
                step_id="start_addon",
                progress_action="start_addon",
                progress_task=self.start_task,
            )

        try:
            await self.start_task
        except (FailedConnect, AddonError, AbortFlow) as err:
            LOGGER.error(err)
            if self._running_in_background:
                return await self.async_step_start_failed()
            return self.async_show_progress_done(next_step_id="start_failed")
        finally:
            self.start_task = None

        if self._running_in_background:
            return await self.async_step_finish_addon_setup()
        return self.async_show_progress_done(next_step_id="finish_addon_setup")

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add-on start failed."""
        return self.async_abort(reason="addon_start_failed")

    async def _async_start_addon(self) -> None:
        """Start the Matter Server add-on."""
        addon_manager: AddonManager = get_addon_manager(self.hass)

        await addon_manager.async_schedule_start_addon()
        # Sleep some seconds to let the add-on start properly before connecting.
        for _ in range(ADDON_SETUP_TIMEOUT_ROUNDS):
            await asyncio.sleep(ADDON_SETUP_TIMEOUT)
            try:
                if not (ws_address := self.ws_address):
                    discovery_info = await self._async_get_addon_discovery_info()
                    ws_address = self.ws_address = build_ws_address(
                        discovery_info["host"], discovery_info["port"]
                    )
                await validate_input(self.hass, {CONF_URL: ws_address})
            except (AbortFlow, CannotConnect) as err:
                LOGGER.debug(
                    "Add-on not ready yet, waiting %s seconds: %s",
                    ADDON_SETUP_TIMEOUT,
                    err,
                )
            else:
                break
        else:
            raise FailedConnect("Failed to start Matter Server add-on: timeout")

    async def _async_get_addon_info(self) -> AddonInfo:
        """Return Matter Server add-on info."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            addon_info: AddonInfo = await addon_manager.async_get_addon_info()
        except AddonError as err:
            LOGGER.error(err)
            raise AbortFlow("addon_info_failed") from err

        return addon_info

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if is_hassio(self.hass):
            return await self.async_step_on_supervisor()

        return await self.async_step_manual()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a manual configuration."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual", data_schema=get_manual_schema({})
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidServerVersion:
            errors["base"] = "invalid_server_version"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.ws_address = user_input[CONF_URL]

            return await self._async_create_entry_or_abort()

        return self.async_show_form(
            step_id="manual", data_schema=get_manual_schema(user_input), errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        if not async_is_onboarded(self.hass) and is_hassio(self.hass):
            await self._async_handle_discovery_without_unique_id()
            self._running_in_background = True
            return await self.async_step_on_supervisor(
                user_input={CONF_USE_ADDON: True}
            )
        return await self._async_step_discovery_without_unique_id()

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Receive configuration from add-on discovery info.

        This flow is triggered by the Matter Server add-on.
        """
        if discovery_info.slug != ADDON_SLUG:
            return self.async_abort(reason="not_matter_addon")

        await self._async_handle_discovery_without_unique_id()

        self.ws_address = build_ws_address(
            discovery_info.config["host"], discovery_info.config["port"]
        )

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the add-on discovery."""
        if user_input is not None:
            return await self.async_step_on_supervisor(
                user_input={CONF_USE_ADDON: True}
            )

        return self.async_show_form(step_id="hassio_confirm")

    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle logic when on Supervisor host."""
        if user_input is None:
            return self.async_show_form(
                step_id="on_supervisor", data_schema=ON_SUPERVISOR_SCHEMA
            )
        if not user_input[CONF_USE_ADDON]:
            return await self.async_step_manual()

        self.use_addon = True

        addon_info = await self._async_get_addon_info()

        if addon_info.state == AddonState.RUNNING:
            return await self.async_step_finish_addon_setup()

        if addon_info.state == AddonState.NOT_RUNNING:
            return await self.async_step_start_addon()

        return await self.async_step_install_addon()

    async def async_step_finish_addon_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare info needed to complete the config entry."""
        if not self.ws_address:
            discovery_info = await self._async_get_addon_discovery_info()
            ws_address = self.ws_address = build_ws_address(
                discovery_info["host"], discovery_info["port"]
            )
            # Check that we can connect to the address.
            try:
                await validate_input(self.hass, {CONF_URL: ws_address})
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")

        return await self._async_create_entry_or_abort()

    async def _async_create_entry_or_abort(self) -> ConfigFlowResult:
        """Return a config entry for the flow or abort if already configured."""
        assert self.ws_address is not None

        if existing_config_entries := self._async_current_entries():
            config_entry = existing_config_entries[0]
            self.hass.config_entries.async_update_entry(
                config_entry,
                data={
                    **config_entry.data,
                    CONF_URL: self.ws_address,
                    CONF_USE_ADDON: self.use_addon,
                    CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon,
                },
                title=DEFAULT_TITLE,
            )
            await self.hass.config_entries.async_reload(config_entry.entry_id)
            raise AbortFlow("reconfiguration_successful")

        # Abort any other flows that may be in progress
        for progress in self._async_in_progress():
            self.hass.config_entries.flow.async_abort(progress["flow_id"])

        return self.async_create_entry(
            title=DEFAULT_TITLE,
            data={
                CONF_URL: self.ws_address,
                CONF_USE_ADDON: self.use_addon,
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon,
            },
        )


class FailedConnect(HomeAssistantError):
    """Failed to connect to the Matter Server."""
