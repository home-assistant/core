"""Config flow for WattTime integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from aiowatttime import Client
from aiowatttime.errors import CoordinatesNotFoundError, InvalidCredentialsError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_SHOW_ON_MAP,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import (
    CONF_BALANCING_AUTHORITY,
    CONF_BALANCING_AUTHORITY_ABBREV,
    DOMAIN,
    LOGGER,
)

CONF_LOCATION_TYPE = "location_type"

LOCATION_TYPE_COORDINATES = "Specify coordinates"
LOCATION_TYPE_HOME = "Use home location"

STEP_COORDINATES_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LATITUDE): cv.latitude,
        vol.Required(CONF_LONGITUDE): cv.longitude,
    }
)

STEP_LOCATION_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOCATION_TYPE): vol.In(
            [LOCATION_TYPE_HOME, LOCATION_TYPE_COORDINATES]
        ),
    }
)

STEP_REAUTH_CONFIRM_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


@callback
def get_unique_id(data: dict[str, Any]) -> str:
    """Get a unique ID from a data payload."""
    return f"{data[CONF_LATITUDE]}, {data[CONF_LONGITUDE]}"


class WattTimeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WattTime."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._client: Client | None = None
        self._data: dict[str, Any] = {}

    async def _async_validate_credentials(
        self, username: str, password: str, error_step_id: str, error_schema: vol.Schema
    ) -> ConfigFlowResult:
        """Validate input credentials and proceed accordingly."""
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            self._client = await Client.async_login(username, password, session=session)
        except InvalidCredentialsError:
            return self.async_show_form(
                step_id=error_step_id,
                data_schema=error_schema,
                errors={"base": "invalid_auth"},
                description_placeholders={CONF_USERNAME: username},
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unexpected exception while logging in: %s", err)
            return self.async_show_form(
                step_id=error_step_id,
                data_schema=error_schema,
                errors={"base": "unknown"},
                description_placeholders={CONF_USERNAME: username},
            )

        if CONF_LATITUDE in self._data:
            # If coordinates already exist at this stage, we're in an existing flow and
            # should reauth:
            entry_unique_id = get_unique_id(self._data)
            if existing_entry := await self.async_set_unique_id(entry_unique_id):
                self.hass.config_entries.async_update_entry(
                    existing_entry, data=self._data
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(existing_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        # ...otherwise, we're in a new flow:
        self._data[CONF_USERNAME] = username
        self._data[CONF_PASSWORD] = password
        return await self.async_step_location()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Define the config flow to handle options."""
        return WattTimeOptionsFlowHandler(config_entry)

    async def async_step_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the coordinates step."""
        if not user_input:
            return self.async_show_form(
                step_id="coordinates", data_schema=STEP_COORDINATES_DATA_SCHEMA
            )

        if TYPE_CHECKING:
            assert self._client

        unique_id = get_unique_id(user_input)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        try:
            grid_region = await self._client.emissions.async_get_grid_region(
                user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE]
            )
        except CoordinatesNotFoundError:
            return self.async_show_form(
                step_id="coordinates",
                data_schema=STEP_COORDINATES_DATA_SCHEMA,
                errors={CONF_LATITUDE: "unknown_coordinates"},
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unexpected exception while getting region: %s", err)
            return self.async_show_form(
                step_id="coordinates",
                data_schema=STEP_COORDINATES_DATA_SCHEMA,
                errors={"base": "unknown"},
            )

        return self.async_create_entry(
            title=unique_id,
            data={
                CONF_USERNAME: self._data[CONF_USERNAME],
                CONF_PASSWORD: self._data[CONF_PASSWORD],
                CONF_LATITUDE: user_input[CONF_LATITUDE],
                CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                CONF_BALANCING_AUTHORITY: grid_region["name"],
                CONF_BALANCING_AUTHORITY_ABBREV: grid_region["abbrev"],
            },
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the "pick a location" step."""
        if not user_input:
            return self.async_show_form(
                step_id="location", data_schema=STEP_LOCATION_DATA_SCHEMA
            )

        if user_input[CONF_LOCATION_TYPE] == LOCATION_TYPE_HOME:
            return await self.async_step_coordinates(
                {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                }
            )
        return await self.async_step_coordinates()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._data = {**entry_data}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_CONFIRM_DATA_SCHEMA,
                description_placeholders={CONF_USERNAME: self._data[CONF_USERNAME]},
            )

        self._data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

        return await self._async_validate_credentials(
            self._data[CONF_USERNAME],
            self._data[CONF_PASSWORD],
            "reauth_confirm",
            STEP_REAUTH_CONFIRM_DATA_SCHEMA,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        return await self._async_validate_credentials(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            "user",
            STEP_USER_DATA_SCHEMA,
        )


class WattTimeOptionsFlowHandler(OptionsFlow):
    """Handle a WattTime options flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SHOW_ON_MAP,
                        default=self.entry.options.get(CONF_SHOW_ON_MAP, True),
                    ): bool
                }
            ),
        )
