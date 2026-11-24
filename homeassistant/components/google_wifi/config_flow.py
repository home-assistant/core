"""Config flow for Google Wifi."""

import logging
from typing import Any, override

from googlewifiapi import GoogleWifiAPI
from googlewifiapi.exception import GoogleWifiClientError, GoogleWifiDataValidationError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    }
)
RECONFIGURE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): cv.string,
    }
)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the device."""


class InvalidResponse(HomeAssistantError):
    """Error to indicate the device did not return Google Wifi status."""


async def async_get_hardware_id(hass: HomeAssistant, host: str) -> str:
    """Connect to a Google Wifi device and return its hardware id."""
    api = GoogleWifiAPI(host, sess=async_get_clientsession(hass))
    try:
        status = await api.async_update()
    except GoogleWifiClientError as err:
        raise CannotConnect from err
    except GoogleWifiDataValidationError as err:
        raise InvalidResponse from err

    if not status.system.hardware_id:
        raise InvalidResponse
    return status.system.hardware_id


class GoogleWifiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Wifi."""

    VERSION = 1

    def _async_align_title_with_host(self, hardware_id: str, host: str) -> None:
        """Rename an entry that is still titled with its previous host."""
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, hardware_id
        )
        if entry is not None and entry.title == entry.data[CONF_HOST]:
            self.hass.config_entries.async_update_entry(entry, title=host)

    async def _async_handle_host(self, host: str) -> tuple[str | None, dict[str, str]]:
        """Validate a host and return its hardware id or a form error."""
        try:
            return await async_get_hardware_id(self.hass, host), {}
        except CannotConnect:
            return None, {"base": "cannot_connect"}
        except InvalidResponse:
            return None, {"base": "invalid_response"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return None, {"base": "unknown"}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            hardware_id, errors = await self._async_handle_host(host)
            if hardware_id is not None:
                self._async_align_title_with_host(hardware_id, host)
                await self.async_set_unique_id(hardware_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(title=host, data={CONF_HOST: host})

        schema = USER_DATA_SCHEMA
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(
                schema, {CONF_HOST: user_input[CONF_HOST].strip()}
            )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the host of an existing device to be changed."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            hardware_id, errors = await self._async_handle_host(host)
            if hardware_id is not None:
                await self.async_set_unique_id(hardware_id)
                self._abort_if_unique_id_mismatch(reason="unique_id_mismatch")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_HOST: host},
                    title=host if entry.title == entry.data[CONF_HOST] else entry.title,
                )

        suggested = (
            {CONF_HOST: user_input[CONF_HOST].strip()}
            if user_input is not None
            else {CONF_HOST: entry.data[CONF_HOST]}
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA, suggested
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a YAML sensor platform configuration."""
        _LOGGER.warning(
            "Configuring Google Wifi via YAML is deprecated and will be removed; "
            "Home Assistant will attempt to import it into a config entry"
        )
        host = import_data[CONF_HOST].strip()
        try:
            hardware_id = await async_get_hardware_id(self.hass, host)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidResponse:
            return self.async_abort(reason="invalid_response")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(hardware_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        name = (import_data.get(CONF_NAME) or "").strip() or host
        return self.async_create_entry(title=name, data={CONF_HOST: host})
