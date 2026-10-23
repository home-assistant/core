"""Config flow to configure the eGauge integration."""

from collections.abc import Mapping
from typing import Any, override

from egauge_async.exceptions import EgaugeAuthenticationError, EgaugePermissionError
from egauge_async.json.client import EgaugeJsonClient
from httpx2 import ConnectError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
        probatio.Required(CONF_SSL, default=True): bool,
        probatio.Required(CONF_VERIFY_SSL, default=False): bool,
    }
)
STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class EgaugeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an eGauge config flow."""

    async def _async_validate_input(
        self, data: Mapping[str, Any], errors: dict[str, str]
    ) -> tuple[str, str] | None:
        """Return the serial number and hostname, or None and fill in errors."""
        client = EgaugeJsonClient(
            host=data[CONF_HOST],
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            client=get_async_client(self.hass, verify_ssl=data[CONF_VERIFY_SSL]),
            use_ssl=data[CONF_SSL],
        )
        try:
            serial_number = await client.get_device_serial_number()
            hostname = await client.get_hostname()
        except EgaugeAuthenticationError:
            errors["base"] = "invalid_auth"
        except EgaugePermissionError:
            errors["base"] = "missing_permission"
        except ConnectError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return serial_number, hostname
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None and (
            info := await self._async_validate_input(user_input, errors)
        ):
            serial_number, hostname = info
            await self.async_set_unique_id(serial_number)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=hostname, data=user_input)

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
        """Handle reauthentication upon an authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None and (
            info := await self._async_validate_input(
                {**reauth_entry.data, **user_input}, errors
            )
        ):
            await self.async_set_unique_id(info[0])
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                reauth_entry, data_updates=user_input
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                CONF_HOST: reauth_entry.data[CONF_HOST],
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
            },
        )
