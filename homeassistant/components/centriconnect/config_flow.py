"""Config flow for the CentriConnect/MyPropane API integration."""

from collections.abc import Callable, Mapping
import logging
from typing import Any, override

from aiocentriconnect import CentriConnect
from aiocentriconnect.exceptions import (
    CentriConnectConnectionError,
    CentriConnectDecodeError,
    CentriConnectEmptyResponseError,
    CentriConnectNotFoundError,
    CentriConnectTooManyRequestsError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CENTRICONNECT_DEVICE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_RECONFIGURE_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTHENTICATE_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_DEVICE_ID): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # Validate the user-supplied data can be used to set up a connection.
    hub = CentriConnect(
        data[CONF_USERNAME],
        data[CONF_DEVICE_ID],
        data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    tank_data = await hub.async_get_tank_data()

    # Return info to store in the config entry.
    return {
        "title": tank_data.device_name,
        CENTRICONNECT_DEVICE_ID: tank_data.device_id,
    }


class CentriConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CentriConnect/MyPropane API."""

    VERSION = 1
    _device_id: str | None = None

    async def _handle_flow(
        self,
        step_id: str,
        data_schema: probatio.Schema,
        user_input: dict[str, Any] | None,
        update_user_input: Callable[[dict[str, Any]], dict[str, Any]],
        on_success: Callable[[dict[str, Any], dict[str, Any]], ConfigFlowResult],
    ) -> ConfigFlowResult:
        """Handle the flow for both user and reconfigure steps."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, update_user_input(user_input))
            except (
                CentriConnectConnectionError,
                CentriConnectTooManyRequestsError,
            ):
                errors["base"] = "cannot_connect"
            except CentriConnectNotFoundError:
                errors["base"] = "invalid_auth"
            except CentriConnectEmptyResponseError, CentriConnectDecodeError:
                errors["base"] = "unknown"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    unique_id=info[CENTRICONNECT_DEVICE_ID], raise_on_progress=True
                )
                return on_success(info, user_input)

        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        old_entry = self._get_reconfigure_entry()

        def _on_success(
            info: dict[str, Any], user_input: dict[str, Any]
        ) -> ConfigFlowResult:
            self._abort_if_unique_id_mismatch(reason="wrong_device")
            return self.async_update_reload_and_abort(
                old_entry, data_updates=user_input
            )

        return await self._handle_flow(
            step_id="reconfigure",
            data_schema=STEP_RECONFIGURE_DATA_SCHEMA,
            user_input=user_input,
            update_user_input=lambda user_input: {
                **user_input,
                CONF_DEVICE_ID: old_entry.data[CONF_DEVICE_ID],
            },
            on_success=_on_success,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._device_id = entry_data[CONF_DEVICE_ID]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""

        def _on_success(
            info: dict[str, Any], user_input: dict[str, Any]
        ) -> ConfigFlowResult:
            self._abort_if_unique_id_mismatch(reason="wrong_device")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=user_input
            )

        return await self._handle_flow(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTHENTICATE_DATA_SCHEMA,
            user_input=user_input,
            update_user_input=lambda user_input: {
                **user_input,
                CONF_DEVICE_ID: self._device_id,
            },
            on_success=_on_success,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        def _on_success(
            info: dict[str, Any], user_input: dict[str, Any]
        ) -> ConfigFlowResult:
            self._abort_if_unique_id_configured(
                updates=user_input, reload_on_update=True
            )
            return self.async_create_entry(title=info["title"], data=user_input)

        return await self._handle_flow(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            user_input=user_input,
            update_user_input=lambda user_input: user_input,
            on_success=_on_success,
        )
