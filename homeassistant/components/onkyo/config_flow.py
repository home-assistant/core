"""Config flow for Onkyo."""

from collections.abc import Mapping
import logging
from typing import Any

import eiscp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.util.network import is_ip_address

from .const import BRAND_NAME, DOMAIN

FlowInput = Mapping[str, Any] | None

_LOGGER = logging.getLogger(__name__)

CONF_DEVICE = "device"


class OnkyoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Onkyo config flow."""

    VERSION = 2
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, eiscp.eISCP] = {}

    def _get_device_name(self, receiver: eiscp.eISCP) -> str:
        return f'{receiver.info["model_name"]} ({receiver.info["identifier"]})'

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to pick discovered device."""

        if user_input is not None:
            receiver = self._discovered_devices[user_input[CONF_DEVICE]]
            await self.async_set_unique_id(
                receiver.info["identifier"], raise_on_progress=False
            )

            return self.async_create_entry(
                title=self._get_device_name(receiver),
                data={CONF_HOST: receiver.host},
            )

        current_unique_ids = self._async_current_ids()
        current_hosts = {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
        }
        discovered_devices = eiscp.eISCP.discover()
        _LOGGER.debug("eISCP discovery result: %s", discovered_devices)

        self._discovered_devices = {
            device.info["identifier"]: device for device in discovered_devices
        }

        devices_name = {
            device.info[
                "identifier"
            ]: f"{BRAND_NAME} {device.info["model_name"]} ({device.host}:{device.port})"
            for host, device in self._discovered_devices.items()
            if device.info["identifier"] not in current_unique_ids
            and host not in current_hosts
        }

        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            if not (host := user_input[CONF_HOST]):
                _LOGGER.debug("Manual input: %s", host)
                return await self.async_step_pick_device()

            if not is_ip_address(user_input[CONF_HOST]):
                errors["base"] = "no_ip"
            else:
                try:
                    receiver = eiscp.eISCP(user_input[CONF_HOST], user_input[CONF_PORT])
                    # receiver.info["identifier"] += "TEST"
                    identifier = receiver.info["identifier"]
                except TypeError:
                    # Info is None when connection fails
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(identifier, raise_on_progress=False)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: user_input[CONF_HOST]}
                    )

                    user_input[CONF_NAME] = self._get_device_name(receiver)
                    return self.async_create_entry(
                        title=self._get_device_name(receiver),
                        data=user_input,
                    )
                finally:
                    receiver.disconnect()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HOST, default=""): str,
                    vol.Optional(CONF_PORT, default=60128): int,
                }
            ),
            errors=errors,
        )
