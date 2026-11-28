"""Config flow for the Moulinex integration."""

from typing import TYPE_CHECKING, Any, override

from aiomoulinex import (
    COUNTRIES,
    LoginError,
    MoulinexAuthenticationError,
    MoulinexConnectionError,
    Region,
    Tokens,
    fetch_profile,
    login,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY, CONF_EMAIL, CONF_PASSWORD, CONF_REGION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    CountrySelector,
    CountrySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_TOKENS, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_COUNTRY): CountrySelector(
            CountrySelectorConfig(countries=list(COUNTRIES))
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

    def __init__(self) -> None:
        """Initialize the flow."""
        self._user_input: dict[str, Any] = {}
        self._tokens: Tokens | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Log in with the account of the appliances."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._user_input = user_input
            regions = Region.for_country(user_input[CONF_COUNTRY])
            if len(regions) > 1:
                return await self.async_step_region()
            if (error := await self._async_log_in(regions[0])) is None:
                return self._async_create_entry(regions[0])
            errors["base"] = error

        return self._async_show_user_form(errors)

    async def async_step_region(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the region of a country served by several regions."""
        errors: dict[str, str] = {}
        regions = Region.for_country(self._user_input[CONF_COUNTRY])
        if user_input is not None:
            region = Region(user_input[CONF_REGION])
            if (error := await self._async_log_in(region)) is None:
                return self._async_create_entry(region)
            if error != "no_appliances":
                return self._async_show_user_form({"base": error})
            errors["base"] = error

        return self.async_show_form(
            step_id="region",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_REGION, default=regions[0]): SelectSelector(
                        SelectSelectorConfig(
                            options=[region.value for region in regions],
                            mode=SelectSelectorMode.LIST,
                            translation_key=CONF_REGION,
                        )
                    )
                }
            ),
            errors=errors,
        )

    def _async_show_user_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Show the login form."""
        suggested_values = dict(self._user_input)
        if not suggested_values and self.hass.config.country in COUNTRIES:
            suggested_values[CONF_COUNTRY] = self.hass.config.country
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def _async_log_in(self, region: Region) -> str | None:
        """Log in to the region and return the error, if any."""
        session = async_get_clientsession(self.hass)
        try:
            tokens = await login(
                session,
                self._user_input[CONF_EMAIL],
                self._user_input[CONF_PASSWORD],
                region,
            )
            profile = await fetch_profile(session, tokens.access_token, region)
        except LoginError as err:
            return err.reason.value
        except MoulinexAuthenticationError:
            return "invalid_auth"
        except MoulinexConnectionError:
            return "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return "unknown"
        await self.async_set_unique_id(tokens.user_id)
        self._abort_if_unique_id_configured()
        if not profile.appliances:
            return "no_appliances"
        self._tokens = tokens
        return None

    def _async_create_entry(self, region: Region) -> ConfigFlowResult:
        """Create the entry of the account."""
        if TYPE_CHECKING:
            assert self._tokens is not None
        return self.async_create_entry(
            title=self._user_input[CONF_EMAIL],
            data={
                CONF_REGION: region.value,
                CONF_EMAIL: self._user_input[CONF_EMAIL],
                CONF_TOKENS: self._tokens.to_dict(),
            },
        )
