"""Config flow for the MAWAQIT integration."""

from typing import Any, override

from mawaqit import AsyncMawaqitClient, AuthenticationError, MawaqitError
from mawaqit.types import Mosque
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_EMAIL, CONF_PASSWORD, CONF_UUID
from homeassistant.helpers import selector
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, MAWAQIT_URL

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
        ),
        probatio.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


def _display_name(mosque: Mosque) -> str:
    """Return the name of a mosque with its distance."""
    if mosque.proximity is None:
        return mosque.label
    return f"{mosque.label} ({mosque.proximity / 1000:.2f} km)"


class MawaqitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for MAWAQIT."""

    VERSION = 1

    _client: AsyncMawaqitClient
    _token: str

    def __init__(self) -> None:
        """Initialize the flow."""
        self._mosques: dict[str, Mosque] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Log in to MAWAQIT."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._client = AsyncMawaqitClient(http_client=get_async_client(self.hass))
            try:
                account = await self._client.auth.login(
                    email=user_input[CONF_EMAIL], password=user_input[CONF_PASSWORD]
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except MawaqitError:
                errors["base"] = "cannot_connect"
            else:
                self._token = account.api_access_token
                return await self.async_step_mosques_coordinates()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
            description_placeholders={"mawaqit_url": MAWAQIT_URL},
        )

    async def async_step_mosques_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a mosque near the Home Assistant location."""
        if user_input is not None:
            mosque = self._mosques[user_input[CONF_UUID]]
            return self.async_create_entry(
                title=mosque.label,
                data={CONF_API_KEY: self._token, CONF_UUID: mosque.uuid},
            )

        try:
            mosques = await self._client.mosques.search(
                lat=self.hass.config.latitude, lon=self.hass.config.longitude
            )
        except MawaqitError:
            return self.async_abort(reason="cannot_connect")
        if not mosques:
            return self.async_abort(reason="no_mosque")
        self._mosques = {mosque.uuid: mosque for mosque in mosques}

        return self.async_show_form(
            step_id="mosques_coordinates",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_UUID): probatio.In(
                        {uuid: _display_name(m) for uuid, m in self._mosques.items()}
                    ),
                }
            ),
        )
