"""Config flow for Onkyo."""

from collections.abc import Mapping
import logging
from typing import Any

import eiscp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import ObjectSelector
from homeassistant.util.network import is_ip_address

from .const import (
    BRAND_NAME,
    CONF_DEVICE,
    CONF_EISCP,
    CONF_EISCP_DEFAULT,
    CONF_MAXIMUM_VOLUME,
    CONF_MAXIMUM_VOLUME_DEFAULT,
    CONF_RECEIVER_MAXIMUM_VOLUME,
    CONF_RECEIVER_MAXIMUM_VOLUME_DEFAULT,
    CONF_SOURCES,
    CONF_SOURCES_DEFAULT,
    DOMAIN,
    EISCP_IDENTIFIER,
    EISCP_MODEL_NAME,
)

FlowInput = Mapping[str, Any] | None

_LOGGER = logging.getLogger(__name__)


class OnkyoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Onkyo config flow."""

    VERSION = 2
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, eiscp.eISCP] = {}

    def _get_device_name(self, receiver: eiscp.eISCP) -> str:
        return f'{receiver.info["model_name"]} ({receiver.info[EISCP_IDENTIFIER]})'

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
                except TypeError:
                    # Info is None when connection fails
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(
                        receiver.info[EISCP_IDENTIFIER], raise_on_progress=False
                    )
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: user_input[CONF_HOST]}
                    )

                    return self.async_create_entry(
                        title=self._get_device_name(receiver),
                        data={
                            CONF_HOST: user_input[CONF_HOST],
                            CONF_NAME: self._get_device_name(receiver),
                        },
                    )
                finally:
                    receiver.disconnect()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HOST, default=""): str,
                    vol.Optional(CONF_PORT, default=60128): cv.port,
                }
            ),
            errors=errors,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to pick discovered device."""

        if user_input is not None:
            receiver = self._discovered_devices[user_input[CONF_DEVICE]]
            await self.async_set_unique_id(
                receiver.info[EISCP_IDENTIFIER], raise_on_progress=False
            )

            name = self._get_device_name(receiver)
            return self.async_create_entry(
                title=name, data={CONF_HOST: receiver.host, CONF_NAME: name}
            )

        current_unique_ids = self._async_current_ids()
        current_hosts = {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
        }
        discovered_devices = eiscp.eISCP.discover()
        _LOGGER.debug("eISCP discovery result: %s", discovered_devices)

        self._discovered_devices = {
            device.info[EISCP_IDENTIFIER]: device for device in discovered_devices
        }

        devices_name = {
            device.info[
                EISCP_IDENTIFIER
            ]: f"{BRAND_NAME} {device.info[EISCP_MODEL_NAME]} ({device.host}:{device.port})"
            for host, device in self._discovered_devices.items()
            if device.info[EISCP_IDENTIFIER] not in current_unique_ids
            and host not in current_hosts
        }

        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        return OnkyoOptionsFlowHandler(config_entry)


class OnkyoOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle an options flow for Onkyo."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""

        if user_input is not None:
            try:
                SCHEMA_SOURCES = vol.Schema({str: str})
                SCHEMA_SOURCES(user_input.get(CONF_SOURCES))
            except vol.error.MultipleInvalid:
                return self.async_abort(reason="invalid_sources")

            try:
                SCHEMA_EISCP = vol.Schema({str: [str]})
                SCHEMA_EISCP(user_input.get(CONF_EISCP))
            except vol.error.MultipleInvalid:
                return self.async_abort(reason="invalid_eiscp")

            return self.async_create_entry(data=user_input)

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MAXIMUM_VOLUME, default=CONF_MAXIMUM_VOLUME_DEFAULT
                ): vol.All(cv.positive_int, vol.Range(min=0, max=100)),
                vol.Required(
                    CONF_RECEIVER_MAXIMUM_VOLUME,
                    default=CONF_RECEIVER_MAXIMUM_VOLUME_DEFAULT,
                ): vol.All(cv.positive_int, vol.In([80, 200])),
                vol.Required(
                    CONF_SOURCES, default=CONF_SOURCES_DEFAULT
                ): ObjectSelector(),
                vol.Required(CONF_EISCP, default=CONF_EISCP_DEFAULT): ObjectSelector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                options_schema, self.config_entry.options
            ),
        )
