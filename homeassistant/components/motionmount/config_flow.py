"""Config flow for Vogel's MotionMount."""

import asyncio
from collections.abc import Mapping
import logging
import socket
from typing import Any

import motionmount
import voluptuous as vol

from homeassistant.config_entries import (
    DEFAULT_DISCOVERY_UNIQUE_ID,
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_PORT, CONF_UUID
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN, EMPTY_MAC

_LOGGER = logging.getLogger(__name__)


# A MotionMount can be in four states:
# 1. Old CE and old Pro FW -> It doesn't supply any kind of mac
# 2. Old CE but new Pro FW -> It supplies its mac using DNS-SD, but a read of the mac fails
# 3. New CE but old Pro FW -> It doesn't supply the mac using DNS-SD but we can read it (returning the EMPTY_MAC)
# 4. New CE and new Pro FW -> Both DNS-SD and a read gives us the mac
# If we can't get the mac, we use DEFAULT_DISCOVERY_UNIQUE_ID as an ID, so we can always configure a single MotionMount. Most households will only have a single MotionMount
class MotionMountFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Vogel's MotionMount config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the instance."""
        self.connection_data: dict[str, Any] = {}
        self.backoff_task: asyncio.Task | None = None
        self.backoff_time: int = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        self.connection_data.update(user_input)
        info = {}
        try:
            info = await self._validate_input_connect(self.connection_data)
        except (ConnectionError, socket.gaierror):
            return self.async_abort(reason="cannot_connect")
        except TimeoutError:
            return self.async_abort(reason="time_out")
        except motionmount.NotConnectedError:
            return self.async_abort(reason="not_connected")

        # If the device mac is valid we use it, otherwise we use the default id
        if info.get(CONF_UUID, EMPTY_MAC) != EMPTY_MAC:
            unique_id = info[CONF_UUID]
        else:
            unique_id = DEFAULT_DISCOVERY_UNIQUE_ID

        name = info.get(CONF_NAME, self.connection_data[CONF_HOST])
        self.connection_data[CONF_NAME] = name

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self.connection_data[CONF_HOST],
                CONF_PORT: self.connection_data[CONF_PORT],
            }
        )

        if not info[CONF_PIN]:
            # We need a pin to authenticate
            return await self.async_step_auth()
        # No pin is needed
        return self._create_or_update_entry()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        # Extract information from discovery
        host = discovery_info.hostname
        port = discovery_info.port
        zctype = discovery_info.type
        name = discovery_info.name.removesuffix(f".{zctype}")
        unique_id = discovery_info.properties.get("mac")

        self.connection_data.update(
            {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_NAME: name,
            }
        )

        if unique_id:
            # If we already have the unique id, try to set it now
            # so we can avoid probing the device if its already
            # configured or ignored
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: host, CONF_PORT: port}
            )
        else:
            # Avoid probing devices that already have an entry
            self._async_abort_entries_match({CONF_HOST: host})

        self.context.update({"title_placeholders": {"name": name}})

        try:
            info = await self._validate_input_connect(self.connection_data)
        except (ConnectionError, socket.gaierror):
            return self.async_abort(reason="cannot_connect")
        except TimeoutError:
            return self.async_abort(reason="time_out")
        except motionmount.NotConnectedError:
            return self.async_abort(reason="not_connected")

        # If the device supplied as with a valid MAC we use that
        if info.get(CONF_UUID, EMPTY_MAC) != EMPTY_MAC:
            unique_id = info[CONF_UUID]

        if unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: host, CONF_PORT: port}
            )
        else:
            await self._async_handle_discovery_without_unique_id()

        if not info[CONF_PIN]:
            # We need a pin to authenticate
            return await self.async_step_auth()
        # No pin is needed
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a confirmation flow initiated by zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={CONF_NAME: self.connection_data[CONF_NAME]},
                errors={},
            )

        return self._create_or_update_entry()

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        reauth_entry = self._get_reauth_entry()
        self.connection_data.update(reauth_entry.data)
        return await self.async_step_auth()

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle authentication form."""
        errors = {}

        if user_input is not None:
            self.connection_data[CONF_PIN] = user_input[CONF_PIN]

            # Validate pin code
            valid_or_wait_time = await self._validate_input_pin(self.connection_data)
            if valid_or_wait_time is True:
                return self._create_or_update_entry()

            if type(valid_or_wait_time) is int:
                self.backoff_time = valid_or_wait_time
                self.backoff_task = self.hass.async_create_task(
                    self._backoff(valid_or_wait_time)
                )
                return await self.async_step_backoff()

            errors[CONF_PIN] = CONF_PIN

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN): vol.All(int, vol.Range(min=1, max=9999)),
                }
            ),
            errors=errors,
        )

    async def async_step_backoff(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle backoff progress."""
        if not self.backoff_task or self.backoff_task.done():
            self.backoff_task = None
            return self.async_show_progress_done(next_step_id="auth")

        return self.async_show_progress(
            step_id="backoff",
            description_placeholders={
                "timeout": str(self.backoff_time),
            },
            progress_action="progress_action",
            progress_task=self.backoff_task,
        )

    def _create_or_update_entry(self) -> ConfigFlowResult:
        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            return self.async_update_reload_and_abort(
                reauth_entry, data_updates=self.connection_data
            )
        return self.async_create_entry(
            title=self.connection_data[CONF_NAME],
            data=self.connection_data,
        )

    async def _validate_input_connect(self, data: dict) -> dict[str, Any]:
        """Validate the user input allows us to connect."""

        mm = motionmount.MotionMount(data[CONF_HOST], data[CONF_PORT])
        try:
            await mm.connect()
        finally:
            await mm.disconnect()

        return {
            CONF_UUID: format_mac(mm.mac.hex()),
            CONF_NAME: mm.name,
            CONF_PIN: mm.is_authenticated,
        }

    async def _validate_input_pin(self, data: dict) -> bool | int:
        """Validate the user input allows us to authenticate."""

        mm = motionmount.MotionMount(data[CONF_HOST], data[CONF_PORT])
        try:
            await mm.connect()

            can_authenticate = mm.can_authenticate
            if can_authenticate is True:
                await mm.authenticate(data[CONF_PIN])
            else:
                # The backoff is running, return the remaining time
                return can_authenticate
        finally:
            await mm.disconnect()

        can_authenticate = mm.can_authenticate
        if can_authenticate is True:
            return mm.is_authenticated

        return can_authenticate

    def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=23): int,
                }
            ),
            errors=errors or {},
        )

    async def _backoff(self, time: int) -> None:
        while time > 0:
            time -= 1
            self.backoff_time = time
            await asyncio.sleep(1)
