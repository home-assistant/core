"""Config flow for ClimaCell integration."""
import logging
from typing import Any, Dict

from pyclimacell.pyclimacell import (
    CantConnectException,
    ClimaCell,
    InvalidAPIKeyException,
    RateLimitedException,
)
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    CHINA,
    CONF_AQI_COUNTRY,
    CONF_FORECAST_FREQUENCY,
    DAILY,
    DEFAULT_NAME,
    DISABLE_FORECASTS,
    DOMAIN,
    HOURLY,
    USA,
)

_LOGGER = logging.getLogger(__name__)


def _get_config_schema(
    hass: core.HomeAssistant, input_dict: Dict[str, Any] = None
) -> vol.Schema:
    """
    Return schema defaults for init step based on user input/config dict.

    Retain info already provided for future form views by setting them
    as defaults in schema.
    """
    if input_dict is None:
        input_dict = {}

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=input_dict.get(CONF_NAME, DEFAULT_NAME)
            ): str,
            vol.Required(CONF_API_KEY, default=input_dict.get(CONF_API_KEY)): str,
            vol.Inclusive(
                CONF_LATITUDE,
                "location",
                default=input_dict.get(CONF_LATITUDE, hass.config.latitude),
            ): cv.latitude,
            vol.Inclusive(
                CONF_LONGITUDE,
                "location",
                default=input_dict.get(CONF_LONGITUDE, hass.config.longitude),
            ): cv.longitude,
            vol.Optional(
                CONF_FORECAST_FREQUENCY,
                default=input_dict.get(CONF_FORECAST_FREQUENCY, DAILY),
            ): vol.In((DISABLE_FORECASTS, DAILY, HOURLY)),
            vol.Optional(
                CONF_AQI_COUNTRY, default=input_dict.get(CONF_AQI_COUNTRY, USA),
            ): vol.In((USA, CHINA)),
        },
        extra=vol.REMOVE_EXTRA,
    )


class ClimaCellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ClimaCell Weather API."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                unique_id=f"{cv.slugify(user_input[CONF_NAME])}",
                raise_on_progress=True,
            )
            self._abort_if_unique_id_configured()

            try:
                await ClimaCell(
                    user_input[CONF_API_KEY],
                    str(user_input.get(CONF_LATITUDE, self.hass.config.latitude)),
                    str(user_input.get(CONF_LONGITUDE, self.hass.config.longitude)),
                    session=async_get_clientsession(self.hass),
                ).realtime(["temp"])

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            except CantConnectException:
                errors["base"] = "cannot_connect"
            except InvalidAPIKeyException:
                errors[CONF_API_KEY] = "invalid_api_key"
            except RateLimitedException:
                errors["base"] = "rate_limited"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=_get_config_schema(self.hass, user_input),
            errors=errors,
        )

    async def async_step_import(self, import_config: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a configuration.yaml import."""
        # Check if new config entry matches any existing config entries
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if cv.slugify(entry.data[CONF_NAME]) == cv.slugify(
                import_config[CONF_NAME]
            ):
                if (
                    entry.data[CONF_API_KEY].lower()
                    == import_config[CONF_API_KEY].lower()
                ):
                    updated_data = {}
                    keys = entry.data.keys()
                    for key in keys:
                        if (
                            key in import_config
                            and entry.data[key] != import_config[key]
                        ):
                            updated_data[key] = import_config[key]

                    if updated_data:
                        new_data = entry.data.copy()
                        new_data.update(updated_data)
                        self.hass.config_entries.async_update_entry(
                            entry=entry, data=new_data
                        )
                        return self.async_abort(reason="updated_entry")

                    return self.async_abort(reason="already_configured_account")
                else:
                    return self.async_abort(reason="unique_name_required")

        return await self.async_step_user(user_input=import_config)
