"""Config flow for the Homevolt integration."""

from __future__ import annotations

import logging
from typing import Any

from homevolt import Homevolt, HomevoltAuthenticationError, HomevoltConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


class HomevoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homevolt."""

    VERSION = 1
    MINOR_VERSION = 1

    _host: str
    _device_id: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            password = user_input.get(CONF_PASSWORD)
            websession = async_get_clientsession(self.hass)
            client = Homevolt(host, password, websession=websession)
            try:
                await client.update_info()
                device = client.get_device()
                device_id = device.device_id
            except HomevoltAuthenticationError:
                errors["base"] = "invalid_auth"
            except HomevoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Error occurred while connecting to the Homevolt battery"
                )
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Homevolt Local",
                    data={
                        CONF_HOST: host,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Zeroconf discovery: %s", discovery_info)
        self._host = str(discovery_info.ip_address)

        websession = async_get_clientsession(self.hass)
        client = Homevolt(self._host, websession=websession)
        try:
            await client.update_info()
            device = client.get_device()
            self._device_id = device.device_id
        except HomevoltConnectionError:
            return self.async_abort(reason="cannot_connect")
        except HomevoltAuthenticationError:
            # Device requires authentication - proceed to discovery confirm
            # where user can enter password
            self._device_id = discovery_info.hostname.removesuffix(".local.")
        except Exception:
            _LOGGER.exception("Error occurred while connecting to the Homevolt battery")
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        self.context.update(
            {
                "title_placeholders": {
                    "name": "Homevolt",
                }
            }
        )
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery and optionally get password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            password = user_input.get(CONF_PASSWORD)
            websession = async_get_clientsession(self.hass)
            client = Homevolt(self._host, password, websession=websession)
            try:
                await client.update_info()
                device = client.get_device()
                self._device_id = device.device_id
            except HomevoltAuthenticationError:
                errors["base"] = "invalid_auth"
            except HomevoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Error occurred while connecting to the Homevolt battery"
                )
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(self._device_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Homevolt",
                    data={
                        CONF_HOST: self._host,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={
                "host": self._host,
            },
        )
