"""Config flow for solarman integration."""

import logging
from typing import Any

from solarman_opendata.solarman import Solarman
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MODEL, CONF_PORT, CONF_TYPE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_PRODUCT_TYPE,
    CONF_SERIAL,
    CONF_SN,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SolarmanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solarman."""

    VERSION = 1

    host = ""
    model = ""
    device_sn = ""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.client: Solarman

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step via user interface."""
        errors = {}
        if user_input is not None:
            self.host = user_input[CONF_HOST]

            self.client = Solarman(async_get_clientsession(self.hass), self.host, DEFAULT_PORT)

            try:
                config_data = await self.client.get_config()
            except TimeoutError:
                errors["base"] = "timeout"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unknown error occurred while verifying device")
                errors["base"] = "unknown"
            else:
                device_info = config_data.get(CONF_DEVICE, config_data)

                self.device_sn = device_info[CONF_SN]
                self.model = device_info[CONF_TYPE]

                await self.async_set_unique_id(self.device_sn)
                self._abort_if_unique_id_configured()

                if not errors:
                    return self.async_create_entry(
                        title=f"{self.model} ({self.host})",
                        data={
                            CONF_HOST: self.host,
                            CONF_PORT: DEFAULT_PORT,
                            CONF_SN: self.device_sn,
                            CONF_MODEL: self.model,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.host = discovery_info.host

        self.client = Solarman(
            async_get_clientsession(self.hass), self.host, DEFAULT_PORT
        )

        try:
            await self.client.get_config()
        except TimeoutError:
            return self.async_abort(reason="timeout")
        except ConnectionError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unknown error occurred while verifying device")
            return self.async_abort(reason="unknown")

        self.model = discovery_info.properties[CONF_PRODUCT_TYPE]
        self.device_sn = discovery_info.properties[CONF_SERIAL]

        await self.async_set_unique_id(self.device_sn)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self.host
        assert self.model
        assert self.device_sn

        if user_input is not None:
            return self.async_create_entry(
                title=f"{self.model} ({self.host})",
                data={
                    CONF_HOST: self.host,
                    CONF_PORT: DEFAULT_PORT,
                    CONF_SN: self.device_sn,
                    CONF_MODEL: self.model,
                },
            )

        self._set_confirm_only()

        name = f"{self.model} ({self.device_sn})"
        self.context["title_placeholders"] = {"name": name}

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                CONF_MODEL: self.model,
                CONF_SN: self.device_sn,
                CONF_HOST: self.host,
            },
        )
