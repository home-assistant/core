"""Config flow for Vogel's MotionMount."""
import logging
import socket
from typing import Any

import motionmount
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_UUID
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, EMPTY_MAC

_LOGGER = logging.getLogger(__name__)


# A MotionMount can be in four states:
# 1. Old CE and old Pro FW -> It doesn't supply any kind of mac
# 2. Old CE but new Pro FW -> It supplies its mac using DNS-SD, but a read of the mac fails
# 3. New CE but old Pro FW -> It doesn't supply the mac using DNS-SD but we can read it (returning the EMPTY_MAC)
# 4. New CE and new Pro FW -> Both DNS-SD and a read gives us the mac
# If we can't get the mac, we use DEFAULT_DISCOVERY_UNIQUE_ID as an ID, so we can always configure a single MotionMount. Most households will only have a single MotionMount
class MotionMountFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Vogel's MotionMount config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the instance."""
        self.discovery_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        info = {}
        try:
            info = await self._validate_input(user_input)
        except (ConnectionError, socket.gaierror):
            return self.async_abort(reason="cannot_connect")
        except TimeoutError:
            return self.async_abort(reason="time_out")
        except motionmount.NotConnectedError:
            return self.async_abort(reason="not_connected")
        except motionmount.MotionMountResponseError:
            # This is most likely due to missing support for the mac address property
            # Abort if the handler has config entries already
            if self._async_current_entries():
                return self.async_abort(reason="already_configured")

            # Otherwise we try to continue with the generic uid
            info[CONF_UUID] = config_entries.DEFAULT_DISCOVERY_UNIQUE_ID

        # If the device mac is valid we use it, otherwise we use the default id
        if info.get(CONF_UUID, EMPTY_MAC) != EMPTY_MAC:
            unique_id = info[CONF_UUID]
        else:
            unique_id = config_entries.DEFAULT_DISCOVERY_UNIQUE_ID

        name = info.get(CONF_NAME, user_input[CONF_HOST])

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
            }
        )

        return self.async_create_entry(title=name, data=user_input)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""

        # Extract information from discovery
        host = discovery_info.hostname
        port = discovery_info.port
        zctype = discovery_info.type
        name = discovery_info.name.removesuffix(f".{zctype}")
        unique_id = discovery_info.properties.get("mac")

        self.discovery_info.update(
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
            info = await self._validate_input(self.discovery_info)
        except (ConnectionError, socket.gaierror):
            return self.async_abort(reason="cannot_connect")
        except TimeoutError:
            return self.async_abort(reason="time_out")
        except motionmount.NotConnectedError:
            return self.async_abort(reason="not_connected")
        except motionmount.MotionMountResponseError:
            info = {}
            # We continue as we want to be able to connect with older FW that does not support MAC address

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

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a confirmation flow initiated by zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={CONF_NAME: self.discovery_info[CONF_NAME]},
                errors={},
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME],
            data=self.discovery_info,
        )

    async def _validate_input(self, data: dict) -> dict[str, Any]:
        """Validate the user input allows us to connect."""

        mm = motionmount.MotionMount(data[CONF_HOST], data[CONF_PORT])
        try:
            await mm.connect()
        finally:
            await mm.disconnect()

        return {CONF_UUID: format_mac(mm.mac.hex()), CONF_NAME: mm.name}

    def _show_setup_form(self, errors: dict[str, str] | None = None) -> FlowResult:
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
