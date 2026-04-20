"""Config flow for the guntamatic integration."""

from __future__ import annotations

import logging
from typing import Any

from guntamatic.heater import Heater, NoSerialException
import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class GuntamaticConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for guntamatic."""

    VERSION = 1
    _discovered_ip: str

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        try:
            heater = Heater(discovery_info.ip)
            data = await self.hass.async_add_executor_job(heater.parse_data)
        except requests.exceptions.RequestException:
            return self.async_abort(reason="cannot_connect")
        except NoSerialException:
            return self.async_abort(reason="bad_data")

        # set serial as unique id for deduplication, ip isn't a good match
        serial = data["serial"][0]
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()
        self._discovered_ip = discovery_info.ip

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title="Guntamatic Heater",
                data={CONF_HOST: self._discovered_ip},
            )

        self._set_confirm_only()
        return self.async_show_form(step_id="discovery_confirm")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                heater = Heater(user_input[CONF_HOST])
                data = await self.hass.async_add_executor_job(heater.parse_data)
            except requests.exceptions.RequestException:
                errors["base"] = "cannot_connect"
            except NoSerialException:
                errors["base"] = "bad_data"

            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # set serial as unique id for deduplication, ip isn't a good match
                serial = data["serial"][0]
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Guntamatic Heater", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
