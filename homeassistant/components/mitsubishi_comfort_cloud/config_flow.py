"""Config flow for Mitsubishi Comfort Cloud."""

from collections.abc import Mapping
import logging
from typing import Any, override

from mitsubishi_comfort import MitsubishiCloudAccount
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError
import probatio

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .helpers import async_discover_devices

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


class MitsubishiComfortCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Mitsubishi Comfort Cloud account."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the account and discover supported cloud devices."""
        return await self._async_handle_credentials(user_input, "user")

    async def _async_handle_credentials(
        self, user_input: dict[str, Any] | None, step_id: str
    ) -> ConfigFlowResult:
        """Validate credentials for setup or reauthentication."""
        errors: dict[str, str] = {}
        if user_input is not None:
            account = MitsubishiCloudAccount(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                await account.login()
                devices = await async_discover_devices(account)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except DeviceConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unexpected error discovering Mitsubishi Comfort Cloud devices"
                )
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(account.user_id)
                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=user_input
                    )
                self._abort_if_unique_id_configured()
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    return self.async_create_entry(
                        title=f"Mitsubishi Comfort Cloud ({user_input[CONF_USERNAME]})",
                        data=user_input,
                    )
        return self.async_show_form(
            step_id=step_id,
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication for the existing account."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the credentials for the existing account."""
        return await self._async_handle_credentials(user_input, "reauth_confirm")
