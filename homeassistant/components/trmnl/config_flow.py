"""Config flow for TRMNL."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from trmnl import TRMNLClient
from trmnl.exceptions import TRMNLAuthenticationError, TRMNLError

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN, LOGGER

STEP_USER_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_API_KEY)): str}
)

TRMNL_ACCOUNT_URL = "https://trmnl.com/account"
UNKNOWN_TRMNL_ACCOUNT = "unknown_trmnl_account"


class TRMNLConfigFlow(ConfigFlow, domain=DOMAIN):
    """TRMNL config flow."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user, reauth, or reconfigure."""
        errors: dict[str, str] = {}
        if user_input:
            session = async_get_clientsession(self.hass)
            client = TRMNLClient(token=user_input[CONF_API_KEY], session=session)
            try:
                user = await client.get_me()
            except TRMNLAuthenticationError:
                errors["base"] = "invalid_auth"
            except TRMNLError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(user.identifier))
                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                    )
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user.name,
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={"account_url": TRMNL_ACCOUNT_URL},
        )

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        # Entries are per account, so use a placeholder to only have one discovery flow
        await self.async_set_unique_id(UNKNOWN_TRMNL_ACCOUNT)
        self._abort_if_unique_id_configured()
        device_registry = dr.async_get(self.hass)
        connection = (
            dr.CONNECTION_NETWORK_MAC,
            dr.format_mac(discovery_info.macaddress),
        )
        for entry in self._async_current_entries(include_ignore=False):
            if device_registry.async_get_device_by_connection(
                connection, entry.entry_id
            ):
                return self.async_abort(reason="already_configured")
        return await self.async_step_user()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user()
