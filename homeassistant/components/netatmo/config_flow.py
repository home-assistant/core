"""Config flow for Netatmo."""

from collections.abc import Mapping
import logging
from typing import Any, override
import uuid

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_SHOW_ON_MAP, CONF_UUID
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.typing import VolDictType

from .api import get_api_scopes
from .const import (
    CONF_AREA_NAME,
    CONF_DISABLED_HOMES,
    CONF_LAT_NE,
    CONF_LAT_SW,
    CONF_LON_NE,
    CONF_LON_SW,
    CONF_NEW_AREA,
    CONF_PUBLIC_MODE,
    CONF_WEATHER_AREAS,
    DOMAIN,
)
from .coordinator import NetatmoConfigEntry

_LOGGER = logging.getLogger(__name__)

# Form-only key: the UI presents enabled homes while the stored option keeps
# disabled ones, so homes added to the account later are enabled by default.
CONF_ENABLED_HOMES = "enabled_homes"


class NetatmoFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Netatmo OAuth2 authentication."""

    DOMAIN = DOMAIN

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: NetatmoConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return NetatmoOptionsFlowHandler(config_entry)

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    @override
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        scopes = get_api_scopes(self.flow_impl.domain)
        return {"scope": " ".join(scopes)}

    @override
    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle a flow start."""
        await self.async_set_unique_id(DOMAIN)
        return await super().async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        return await self.async_step_user()

    @override
    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        existing_entry = await self.async_set_unique_id(DOMAIN)
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return await super().async_oauth_create_entry(data)


class NetatmoOptionsFlowHandler(OptionsFlow):
    """Handle Netatmo options."""

    def __init__(self, config_entry: NetatmoConfigEntry) -> None:
        """Initialize Netatmo options flow."""
        self.options = dict(config_entry.options)
        self.options.setdefault(CONF_WEATHER_AREAS, {})
        self.options.setdefault(CONF_DISABLED_HOMES, [])
        # Homes shown on the last render; None when the selector was not offered
        self._offered_homes: dict[str, str] | None = None

    def _get_all_homes(self) -> dict[str, str]:
        """Return a mapping of home id to home display name."""
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return {}
        all_homes_id = self.config_entry.runtime_data.account.all_homes_id
        return {
            home_id: home_name or home_id for home_id, home_name in all_homes_id.items()
        }

    def _homes_selection_offered(self, homes: dict[str, str]) -> bool:
        """Return if the homes selector is offered for the given homes.

        Also offered with a single home left disabled, so it can be re-enabled.
        """
        return len(homes) > 1 or (
            bool(homes) and bool(self.options[CONF_DISABLED_HOMES])
        )

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Manage the Netatmo options."""
        return await self.async_step_public_weather_areas()

    async def async_step_public_weather_areas(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Manage configuration of Netatmo homes and public weather areas."""
        errors: dict = {}

        if user_input is not None:
            new_client = user_input.pop(CONF_NEW_AREA, None)
            areas = user_input.pop(CONF_WEATHER_AREAS, [])
            user_input[CONF_WEATHER_AREAS] = {
                area: self.options[CONF_WEATHER_AREAS][area] for area in areas
            }

            enabled_homes = user_input.pop(CONF_ENABLED_HOMES, [])
            # Compare against the homes offered on the form, not a fresh
            # fetch: a home added in the meantime must stay enabled by default
            if self._offered_homes is not None:
                if enabled_homes:
                    user_input[CONF_DISABLED_HOMES] = [
                        home_id
                        for home_id in self._offered_homes
                        if home_id not in enabled_homes
                    ]
                else:
                    # An empty selection re-enables all homes
                    user_input[CONF_DISABLED_HOMES] = []

            self.options.update(user_input)
            if new_client:
                return await self.async_step_public_weather(
                    user_input={CONF_NEW_AREA: new_client}
                )

            return self._create_options_entry()

        weather_areas = list(self.options[CONF_WEATHER_AREAS])

        schema: VolDictType = {}

        homes = self._get_all_homes()
        self._offered_homes = homes if self._homes_selection_offered(homes) else None
        if self._offered_homes is not None:
            enabled_homes = [
                home_id
                for home_id in homes
                if home_id not in self.options[CONF_DISABLED_HOMES]
            ]
            schema[vol.Optional(CONF_ENABLED_HOMES, default=enabled_homes)] = (
                cv.multi_select(homes)
            )

        schema.update(
            {
                vol.Optional(
                    CONF_WEATHER_AREAS,
                    default=weather_areas,
                ): cv.multi_select(dict.fromkeys(weather_areas)),
                vol.Optional(CONF_NEW_AREA): str,
            }
        )
        data_schema = vol.Schema(schema)
        return self.async_show_form(
            step_id="public_weather_areas",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_public_weather(self, user_input: dict) -> ConfigFlowResult:
        """Manage configuration of Netatmo public weather sensors."""
        if user_input is not None and CONF_NEW_AREA not in user_input:
            self.options[CONF_WEATHER_AREAS][user_input[CONF_AREA_NAME]] = (
                fix_coordinates(user_input)
            )

            self.options[CONF_WEATHER_AREAS][user_input[CONF_AREA_NAME]][CONF_UUID] = (
                str(uuid.uuid4())
            )

            return await self.async_step_public_weather_areas()

        orig_options = self.config_entry.options.get(CONF_WEATHER_AREAS, {}).get(
            user_input[CONF_NEW_AREA], {}
        )

        default_longitude = self.hass.config.longitude
        default_latitude = self.hass.config.latitude
        default_size = 0.04

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_AREA_NAME, default=user_input[CONF_NEW_AREA]): str,
                vol.Optional(
                    CONF_LAT_NE,
                    default=orig_options.get(
                        CONF_LAT_NE, default_latitude + default_size
                    ),
                ): cv.latitude,
                vol.Optional(
                    CONF_LON_NE,
                    default=orig_options.get(
                        CONF_LON_NE, default_longitude + default_size
                    ),
                ): cv.longitude,
                vol.Optional(
                    CONF_LAT_SW,
                    default=orig_options.get(
                        CONF_LAT_SW, default_latitude - default_size
                    ),
                ): cv.latitude,
                vol.Optional(
                    CONF_LON_SW,
                    default=orig_options.get(
                        CONF_LON_SW, default_longitude - default_size
                    ),
                ): cv.longitude,
                vol.Required(
                    CONF_PUBLIC_MODE,
                    default=orig_options.get(CONF_PUBLIC_MODE, "avg"),
                ): vol.In(["avg", "max", "min"]),
                vol.Required(
                    CONF_SHOW_ON_MAP,
                    default=orig_options.get(CONF_SHOW_ON_MAP, False),
                ): bool,
            }
        )

        return self.async_show_form(step_id="public_weather", data_schema=data_schema)

    def _create_options_entry(self) -> ConfigFlowResult:
        """Update config entry options."""
        return self.async_create_entry(
            title="Netatmo Public Weather", data=self.options
        )


def fix_coordinates(user_input: dict) -> dict:
    """Fix coordinates if they don't comply with the Netatmo API."""
    # Ensure coordinates have acceptable length for the Netatmo API
    for coordinate in (CONF_LAT_NE, CONF_LAT_SW, CONF_LON_NE, CONF_LON_SW):
        if len(str(user_input[coordinate]).split(".")[1]) < 7:
            user_input[coordinate] = user_input[coordinate] + 1e-7

    # Swap coordinates if entered in wrong order
    if user_input[CONF_LAT_NE] < user_input[CONF_LAT_SW]:
        user_input[CONF_LAT_NE], user_input[CONF_LAT_SW] = (
            user_input[CONF_LAT_SW],
            user_input[CONF_LAT_NE],
        )
    if user_input[CONF_LON_NE] < user_input[CONF_LON_SW]:
        user_input[CONF_LON_NE], user_input[CONF_LON_SW] = (
            user_input[CONF_LON_SW],
            user_input[CONF_LON_NE],
        )

    return user_input
