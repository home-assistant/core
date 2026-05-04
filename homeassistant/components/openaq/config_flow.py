"""Config flow for the OpenAQ integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from openaq import (
    ApiKeyMissingError,
    AsyncOpenAQ,
    BadGatewayError,
    BadRequestError,
    ForbiddenError,
    GatewayTimeoutError,
    HTTPRateLimitError,
    NotAuthorizedError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    TimeoutError as OpenAQTimeoutError,
    ValidationError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_LIMIT,
    CONF_LOCATION_ID,
    CONF_RADIUS,
    DEFAULT_LOCATION_LIMIT,
    DEFAULT_RADIUS,
    DOMAIN,
    MAX_RADIUS,
    SUBENTRY_TYPE_LOCATION,
)
from .coordinator import get_openaq_value

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})
LOCATION_ID_DATA_SCHEMA = vol.Schema({vol.Required(CONF_LOCATION_ID): int})


@dataclass(slots=True)
class OpenAQLocationFlowData:
    """OpenAQ location data stored during the subentry flow."""

    location_id: int
    title: str


def _get_client(api_key: str) -> AsyncOpenAQ:
    """Return an OpenAQ client."""
    return AsyncOpenAQ(api_key=api_key)


async def validate_input(_hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    client = _get_client(data[CONF_API_KEY])
    try:
        await client.parameters.list(limit=1)
    except (ApiKeyMissingError, ForbiddenError, NotAuthorizedError) as err:
        raise InvalidAuth from err
    except (HTTPRateLimitError, RateLimitError) as err:
        raise RateLimited from err
    except (
        BadGatewayError,
        BadRequestError,
        GatewayTimeoutError,
        NotFoundError,
        OpenAQTimeoutError,
        ServerError,
        ServiceUnavailableError,
        ValidationError,
    ) as err:
        raise CannotConnect from err
    finally:
        await client.close()


def _location_title(location: object) -> str:
    """Return a display title for an OpenAQ location."""
    name = get_openaq_value(location, "name")
    locality = get_openaq_value(location, "locality")
    if isinstance(locality, str) and locality and locality != name:
        return f"{name}, {locality}"
    return str(name)


def _is_location_configured(hass: HomeAssistant, location_id: int) -> bool:
    """Return whether an OpenAQ location is already configured."""
    unique_id = str(location_id)
    for entry in hass.config_entries.async_entries(DOMAIN):
        for subentry in entry.subentries.values():
            if subentry.unique_id == unique_id:
                return True
    return False


class OpenAQConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenAQ."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_LOCATION: OpenAQLocationSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except RateLimited:
                errors["base"] = "rate_limited"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="OpenAQ",
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class OpenAQLocationSubentryFlow(ConfigSubentryFlow):
    """Handle an OpenAQ location subentry flow."""

    _locations: dict[str, OpenAQLocationFlowData]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select how to add an OpenAQ location."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["map", CONF_LOCATION_ID],
        )

    async def async_step_map(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Find OpenAQ locations near a map point."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = _get_client(self._get_entry().data[CONF_API_KEY])
            try:
                response = await client.locations.list(
                    coordinates=(
                        user_input[CONF_LOCATION][CONF_LATITUDE],
                        user_input[CONF_LOCATION][CONF_LONGITUDE],
                    ),
                    radius=user_input[CONF_RADIUS],
                    limit=user_input[CONF_LIMIT],
                )
            except HTTPRateLimitError, RateLimitError:
                errors["base"] = "rate_limited"
            except (
                BadGatewayError,
                BadRequestError,
                GatewayTimeoutError,
                NotFoundError,
                OpenAQTimeoutError,
                ServerError,
                ServiceUnavailableError,
                ValidationError,
            ):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._locations = {}
                for location in response.results:
                    location_id = get_openaq_value(location, "id")
                    if not isinstance(location_id, int):
                        continue
                    self._locations[str(location_id)] = OpenAQLocationFlowData(
                        location_id=location_id,
                        title=_location_title(location),
                    )
                if not self._locations:
                    errors["base"] = "no_locations_found"
                else:
                    return await self.async_step_select()
            finally:
                await client.close()

        return self.async_show_form(
            step_id="map",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_LOCATION): LocationSelector(
                            LocationSelectorConfig(radius=False)
                        ),
                        vol.Required(CONF_RADIUS, default=DEFAULT_RADIUS): vol.All(
                            vol.Coerce(int), vol.Range(min=1, max=MAX_RADIUS)
                        ),
                        vol.Required(
                            CONF_LIMIT, default=DEFAULT_LOCATION_LIMIT
                        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                    }
                ),
                {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    }
                },
            ),
            errors=errors,
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select one of the found OpenAQ locations."""
        if user_input is not None:
            return self._async_create_location_entry(
                self._locations[user_input[CONF_LOCATION_ID]]
            )

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=location_id, label=location.title
                                )
                                for location_id, location in self._locations.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_location_id(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add an OpenAQ location by location ID."""
        errors: dict[str, str] = {}
        if user_input is not None:
            location_id = user_input[CONF_LOCATION_ID]
            if _is_location_configured(self.hass, location_id):
                return self.async_abort(reason="already_configured")
            client = _get_client(self._get_entry().data[CONF_API_KEY])
            try:
                response = await client.locations.get(location_id)
            except HTTPRateLimitError, RateLimitError:
                errors["base"] = "rate_limited"
            except NotFoundError:
                errors["base"] = "invalid_location"
            except (
                BadGatewayError,
                BadRequestError,
                GatewayTimeoutError,
                OpenAQTimeoutError,
                ServerError,
                ServiceUnavailableError,
                ValidationError,
            ):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                location = response.results[0]
                return self._async_create_location_entry(
                    OpenAQLocationFlowData(
                        location_id=location_id,
                        title=_location_title(location),
                    )
                )
            finally:
                await client.close()

        return self.async_show_form(
            step_id=CONF_LOCATION_ID,
            data_schema=LOCATION_ID_DATA_SCHEMA,
            errors=errors,
        )

    def _async_create_location_entry(
        self, location: OpenAQLocationFlowData
    ) -> SubentryFlowResult:
        """Create an OpenAQ location subentry."""
        if _is_location_configured(self.hass, location.location_id):
            return self.async_abort(reason="already_configured")
        return self.async_create_entry(
            title=location.title,
            data={CONF_LOCATION_ID: location.location_id},
            unique_id=str(location.location_id),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class RateLimited(HomeAssistantError):
    """Error to indicate the API rate limit was exceeded."""
