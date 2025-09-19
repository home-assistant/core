"""Config flow for the Seko PoolDose integration."""

from __future__ import annotations

import logging
from typing import Any

from pooldose.client import PooldoseClient
from pooldose.request_status import RequestStatus
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCHEMA_DEVICE = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    }
)


class PooldoseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Seko Pooldose."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_DEVICE,
            )

        host = user_input[CONF_HOST]
        client = PooldoseClient(host)
        client_status = await client.connect()
        if client_status == RequestStatus.HOST_UNREACHABLE:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_DEVICE,
                errors={"base": "cannot_connect"},
            )
        if client_status == RequestStatus.PARAMS_FETCH_FAILED:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_DEVICE,
                errors={"base": "params_fetch_failed"},
            )
        if client_status != RequestStatus.SUCCESS:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_DEVICE,
                errors={"base": "cannot_connect"},
            )

        api_status, api_versions = client.check_apiversion_supported()
        if api_status == RequestStatus.NO_DATA:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_DEVICE,
                errors={"base": "api_not_set"},
            )
        if api_status == RequestStatus.API_VERSION_UNSUPPORTED:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_DEVICE,
                errors={"base": "api_not_supported"},
                description_placeholders=api_versions,
            )

        device_info = client.device_info
        if not device_info:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_DEVICE,
                errors={"base": "no_device_info"},
            )
        serial_number = device_info.get("SERIAL_NUMBER")
        if not serial_number:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_DEVICE,
                errors={"base": "no_serial_number"},
            )

        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"PoolDose {serial_number}",
            data={CONF_HOST: host},
        )
