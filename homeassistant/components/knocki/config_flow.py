"""Config flow for Knocki integration."""

from collections.abc import Mapping
from typing import Any, override

from knocki import KnockiClient, KnockiConnectionError, KnockiInvalidAuthError
import probatio

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN, LOGGER

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class KnockiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Knocki."""

    async def _async_authenticate(
        self, user_input: dict[str, Any]
    ) -> tuple[str | None, dict[str, str]]:
        """Log in, link the account and return the token or the errors."""
        client = KnockiClient(session=async_get_clientsession(self.hass))
        try:
            token_response = await client.login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            await self.async_set_unique_id(token_response.user_id)
            if self.source == SOURCE_REAUTH:
                self._abort_if_unique_id_mismatch()
            else:
                self._abort_if_unique_id_configured()
            client.token = token_response.token
            await client.link()
        except HomeAssistantError:
            # Catch the unique_id abort and reraise it to keep the code clean
            raise
        except KnockiConnectionError:
            return None, {"base": "cannot_connect"}
        except KnockiInvalidAuthError:
            return None, {"base": "invalid_auth"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Error logging into the Knocki API")
            return None, {"base": "unknown"}
        return token_response.token, {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            token, errors = await self._async_authenticate(user_input)
            if token is not None:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={
                        CONF_TOKEN: token,
                    },
                )
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=DATA_SCHEMA,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with new credentials."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        username = reauth_entry.title
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            token, errors = await self._async_authenticate(user_input)
            if token is not None:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates={CONF_TOKEN: token}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, {CONF_USERNAME: username}
            ),
        )

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a DHCP discovery."""
        device_registry = dr.async_get(self.hass)
        for device in device_registry.async_get_devices(
            identifiers={(DOMAIN, discovery_info.hostname)}
        ):
            device_registry.async_update_device(
                device.id,
                new_connections={
                    (dr.CONNECTION_NETWORK_MAC, discovery_info.macaddress)
                },
            )
        return await super().async_step_dhcp(discovery_info)
