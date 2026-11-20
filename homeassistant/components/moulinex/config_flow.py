"""Config flow for the Moulinex integration."""

from typing import Any, override

from aiomoulinex import (
    LoginError,
    MoulinexAuthenticationError,
    MoulinexConnectionError,
    Region,
    fetch_profile,
    login,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_REGION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_TOKENS, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_REGION, default=Region.MOULINEX_FR): SelectSelector(
            SelectSelectorConfig(
                options=[region.value for region in Region],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_REGION,
            )
        ),
        probatio.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


class MoulinexConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Moulinex."""

    VERSION = 1

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Set up the account of an appliance found on the network."""
        await self._async_handle_discovery_without_unique_id()
        return await self.async_step_user()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Log in with the account of the appliances."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            region = Region(user_input[CONF_REGION])
            try:
                tokens = await login(
                    session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD], region
                )
                user_id = tokens.user_id
                profile = await fetch_profile(session, tokens.access_token, region)
            except LoginError as err:
                errors["base"] = err.reason.value
            except MoulinexAuthenticationError:
                errors["base"] = "invalid_auth"
            except MoulinexConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                if not profile.appliances:
                    return self.async_abort(reason="no_appliances")
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_REGION: user_input[CONF_REGION],
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_TOKENS: tokens.to_dict(),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
