"""Config flow for Tomorrow.io integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from pytomorrowio.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
)
from pytomorrowio.pytomorrowio import TomorrowioV4
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
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
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import (
    CONF_TIMESTEP,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DOMAIN,
    INTEGRATION_NAME,
    SUBENTRY_TYPE_LOCATION,
    TMRW_ATTR_TEMPERATURE,
)
from .entity import async_get_base_unique_id

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


def _get_location_schema(hass: HomeAssistant) -> vol.Schema:
    """Return the schema for a location subentry."""
    return vol.Schema(
        {
            # Name field is no longer allowed in config flow schemas
            # pylint: disable-next=home-assistant-config-flow-name-field
            vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Required(
                CONF_LOCATION,
                default={
                    CONF_LATITUDE: hass.config.latitude,
                    CONF_LONGITUDE: hass.config.longitude,
                },
            ): LocationSelector(LocationSelectorConfig(radius=False)),
            vol.Required(CONF_TIMESTEP, default=DEFAULT_TIMESTEP): vol.In(
                [1, 5, 15, 30, 60]
            ),
        }
    )


def _get_location_unique_id(location: Mapping[str, Any]) -> str:
    """Return the unique ID for a location subentry."""
    return f"{location[CONF_LATITUDE]}_{location[CONF_LONGITUDE]}"


class TomorrowioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tomorrow.io Weather API."""

    VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            await self.async_set_unique_id(api_key)
            self._abort_if_unique_id_configured()

            try:
                await TomorrowioV4(
                    api_key,
                    str(self.hass.config.latitude),
                    str(self.hass.config.longitude),
                    session=async_get_clientsession(self.hass),
                ).realtime([TMRW_ATTR_TEMPERATURE])
            except CantConnectException:
                errors["base"] = "cannot_connect"
            except InvalidAPIKeyException:
                errors[CONF_API_KEY] = "invalid_api_key"
            except RateLimitedException:
                errors[CONF_API_KEY] = "rate_limited"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=INTEGRATION_NAME, data={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "signup_link": "[Tomorrow.io](https://app.tomorrow.io/signup)"
            },
        )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_LOCATION: LocationSubentryFlowHandler}


class LocationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for a location."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle adding or reconfiguring a location."""
        entry = self._get_entry()
        reconfigure_subentry = (
            self._get_reconfigure_subentry()
            if self.source == SOURCE_RECONFIGURE
            else None
        )

        if user_input is not None:
            unique_id = _get_location_unique_id(user_input[CONF_LOCATION])
            if any(
                subentry.unique_id == unique_id
                for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LOCATION)
                if subentry is not reconfigure_subentry
            ):
                return self.async_abort(reason="already_configured")

            if reconfigure_subentry:
                # Entity unique IDs embed the coordinates; moving the
                # location must rewrite them so entities and their history
                # survive instead of being orphaned by the reload.
                api_key: str = entry.data[CONF_API_KEY]
                old_base = async_get_base_unique_id(
                    api_key, reconfigure_subentry.data[CONF_LOCATION]
                )
                new_base = async_get_base_unique_id(api_key, user_input[CONF_LOCATION])
                if new_base != old_base:
                    entity_registry = er.async_get(self.hass)
                    for entity_entry in er.async_entries_for_config_entry(
                        entity_registry, entry.entry_id
                    ):
                        if (
                            entity_entry.config_subentry_id
                            == reconfigure_subentry.subentry_id
                        ):
                            entity_registry.async_update_entity(
                                entity_entry.entity_id,
                                new_unique_id=entity_entry.unique_id.replace(
                                    old_base, new_base, 1
                                ),
                            )
                return self.async_update_and_abort(
                    entry,
                    reconfigure_subentry,
                    title=user_input[CONF_NAME],
                    unique_id=unique_id,
                    data_updates=user_input,
                )

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
                unique_id=unique_id,
            )

        suggested_values: Mapping[str, Any] | None = None
        if reconfigure_subentry:
            suggested_values = {
                CONF_NAME: reconfigure_subentry.data[CONF_NAME],
                CONF_LOCATION: dict(reconfigure_subentry.data[CONF_LOCATION]),
                CONF_TIMESTEP: reconfigure_subentry.data[CONF_TIMESTEP],
            }

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _get_location_schema(self.hass), suggested_values
            ),
        )

    async_step_reconfigure = async_step_user
