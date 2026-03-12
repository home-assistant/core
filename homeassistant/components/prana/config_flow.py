"""Configuration flow for Prana integration."""

import logging
from typing import Any

from prana_local_api_client.exceptions import PranaApiCommunicationError
from prana_local_api_client.models.prana_device_info import PranaDeviceInfo
from prana_local_api_client.prana_api_client import PranaLocalApiClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class PranaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Prana config flow."""

    _host: str
    _device_info: PranaDeviceInfo

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery of a Prana device."""
        _LOGGER.debug("Discovered device via Zeroconf: %s", discovery_info)

        friendly_name = discovery_info.properties.get("label", "")
        self.context["title_placeholders"] = {"name": friendly_name}
        self._host = discovery_info.host

        try:
            self._device_info = await self._validate_device()
        except ValueError:
            return self.async_abort(reason="invalid_device")
        except PranaApiCommunicationError:
            return self.async_abort(reason="invalid_device_or_unreachable")

        self._set_confirm_only()
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None) -> ConfigFlowResult:
        """Handle the user confirming a discovered Prana device."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._device_info.label,
                data={CONF_HOST: self._host},
            )
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._device_info.label,
                "host": self._host,
            },
        )

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manual entry by IP address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            try:
                self._device_info = await self._validate_device()
            except ValueError:
                return self.async_abort(reason="invalid_device")
            except PranaApiCommunicationError:
                errors = {"base": "invalid_device_or_unreachable"}
            if not errors:
                return self.async_create_entry(
                    title=self._device_info.label,
                    data={CONF_HOST: self._host},
                )
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def _validate_device(self) -> PranaDeviceInfo:
        """Validate that a Prana device is reachable and valid."""
        client = PranaLocalApiClient(host=self._host, port=80)
        device_info = await client.get_device_info()

        if not device_info.isValid:
            raise ValueError("invalid_device")

        await self.async_set_unique_id(device_info.manufactureId)
        self._abort_if_unique_id_configured()

        return device_info
