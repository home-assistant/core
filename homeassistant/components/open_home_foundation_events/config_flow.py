"""Config flow for the Open Home Foundation Events integration."""

from typing import Any, override

import probatio

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import DOMAIN, SUBENTRY_TYPE_AREA

DEFAULT_RADIUS = 50000


class OHFEventsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Open Home Foundation Events."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="Open Home Foundation Events", data={})
        return self.async_show_form(step_id="user")

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_AREA: AreaSubentryFlowHandler}


def _get_area_schema(hass: HomeAssistant) -> probatio.Schema:
    """Return the schema for an area, defaulting to the home location."""
    return probatio.Schema(
        {
            # Subentries need a name to be told apart
            # pylint: disable-next=home-assistant-config-flow-name-field
            probatio.Required(CONF_NAME, default=hass.config.location_name): str,
            probatio.Required(
                CONF_LOCATION,
                default={
                    CONF_LATITUDE: hass.config.latitude,
                    CONF_LONGITUDE: hass.config.longitude,
                    CONF_RADIUS: DEFAULT_RADIUS,
                },
            ): LocationSelector(LocationSelectorConfig(radius=True)),
        }
    )


class AreaSubentryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for an area."""

    async def async_step_area(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the area step."""
        if user_input is not None:
            if self.source == SOURCE_USER:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input[CONF_LOCATION]
                )
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=user_input[CONF_NAME],
                data=user_input[CONF_LOCATION],
            )

        suggested: dict[str, Any] = {}
        if self.source != SOURCE_USER:
            subentry = self._get_reconfigure_subentry()
            suggested = {CONF_NAME: subentry.title, CONF_LOCATION: dict(subentry.data)}

        return self.async_show_form(
            step_id="area",
            data_schema=self.add_suggested_values_to_schema(
                _get_area_schema(self.hass), suggested
            ),
        )

    async_step_user = async_step_area
    async_step_reconfigure = async_step_area
