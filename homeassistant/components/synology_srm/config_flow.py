"""Config flow for Synology SRM."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
from requests.exceptions import RequestException
from synology_srm.http import SynologyApiError, SynologyException

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_TRACKED_DEVICES,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .coordinator import create_client

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Required(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        probatio.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


class SynologySrmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Synology SRM."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the device selection."""
        self._data: dict[str, Any] = {}
        self._devices: list[SelectOptionDict] = []

    async def _async_validate_input(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate credentials and fetch the available devices."""
        client = create_client(data)
        try:
            devices = await self.hass.async_add_executor_job(
                client.core.get_network_nsm_device
            )
        except SynologyApiError as err:
            return {
                "base": "invalid_auth"
                if err.code in (400, 401, 402, 403, 404)
                else "cannot_connect"
            }
        except SynologyException, RequestException:
            return {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception connecting to Synology SRM")
            return {"base": "unknown"}
        self._devices = [
            SelectOptionDict(
                value=format_mac(device["mac"]),
                label=f"{device.get('hostname') or device['mac']} ({device['mac']})",
            )
            for device in devices
        ]
        return {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle configuration through the UI."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            errors = await self._async_validate_input(user_input)
            if not errors:
                if not self._devices:
                    errors["base"] = "no_devices_found"
                else:
                    self._data = user_input
                    return await self.async_step_devices()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reauthenticate an existing router."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the updated credentials without changing device selections."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate_input({**entry.data, **user_input})
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(
                            CONF_USERNAME, default=entry.data[CONF_USERNAME]
                        ): str,
                        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the clients to enable, leaving all others disabled."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_TRACKED_DEVICES]:
                self._async_abort_entries_match({CONF_HOST: self._data[CONF_HOST]})
                return self.async_create_entry(
                    title=self._data[CONF_HOST], data={**self._data, **user_input}
                )
            errors["base"] = "no_devices_selected"

        return self.async_show_form(
            step_id="devices",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_TRACKED_DEVICES, default=[]): SelectSelector(
                        SelectSelectorConfig(
                            options=self._devices,
                            multiple=True,
                            sort=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            errors=errors,
        )
