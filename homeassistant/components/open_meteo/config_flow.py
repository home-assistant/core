"""Config flow to configure the Open-Meteo integration."""

from typing import Any, override

from open_meteo import HourlyParameters, OpenMeteo, OpenMeteoError
import probatio

from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ZONE, EntityStateAttribute
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import DOMAIN

_ZONE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ZONE): EntitySelector(
            EntitySelectorConfig(domain=ZONE_DOMAIN),
        ),
    }
)


class OpenMeteoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for OpenMeteo."""

    VERSION = 1
    MINOR_VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_ZONE: user_input[CONF_ZONE]})

            if (zone := self.hass.states.get(user_input[CONF_ZONE])) is None:
                errors[CONF_ZONE] = "zone_not_found"
            else:
                open_meteo = OpenMeteo(session=async_get_clientsession(self.hass))
                try:
                    await open_meteo.forecast(
                        latitude=zone.attributes[EntityStateAttribute.LATITUDE],
                        longitude=zone.attributes[EntityStateAttribute.LONGITUDE],
                        current=[HourlyParameters.TEMPERATURE_2M],
                    )
                except OpenMeteoError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=zone.name,
                        data={CONF_ZONE: user_input[CONF_ZONE]},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_ZONE_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_ZONE: user_input[CONF_ZONE]})

            if (zone := self.hass.states.get(user_input[CONF_ZONE])) is None:
                errors[CONF_ZONE] = "zone_not_found"
            else:
                open_meteo = OpenMeteo(session=async_get_clientsession(self.hass))
                try:
                    await open_meteo.forecast(
                        latitude=zone.attributes[EntityStateAttribute.LATITUDE],
                        longitude=zone.attributes[EntityStateAttribute.LONGITUDE],
                        current=[HourlyParameters.TEMPERATURE_2M],
                    )
                except OpenMeteoError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        title=zone.name,
                        data_updates={CONF_ZONE: user_input[CONF_ZONE]},
                    )

        entry = self._get_reconfigure_entry()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _ZONE_SCHEMA,
                user_input or {CONF_ZONE: entry.data[CONF_ZONE]},
            ),
            errors=errors,
        )
