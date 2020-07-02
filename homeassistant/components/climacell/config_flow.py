"""Config flow for ClimaCell integration."""
import logging
from typing import Any, Dict

from pyclimacell import ClimaCell
from pyclimacell.const import REALTIME
from pyclimacell.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
)
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    CHINA,
    CONF_AQI_COUNTRY,
    CONF_FORECAST_TYPE,
    CONF_TIMESTEP,
    DAILY,
    DEFAULT_AQI_COUNTRY,
    DEFAULT_FORECAST_TYPE,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DISABLE_FORECASTS,
    DOMAIN,
    HOURLY,
    NOWCAST,
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
                CONF_FORECAST_TYPE,
                default=input_dict.get(CONF_FORECAST_TYPE, DEFAULT_FORECAST_TYPE),
            ): vol.In((DISABLE_FORECASTS, DAILY, HOURLY, NOWCAST)),
        },
        extra=vol.REMOVE_EXTRA,
    )


def _get_unique_id(hass: HomeAssistantType, input_dict: Dict[str, Any]):
    """Return unique ID from config data."""
    return (
        f"{input_dict[CONF_API_KEY]}"
        f"_{input_dict.get(CONF_LATITUDE, hass.config.latitude)}"
        f"_{input_dict.get(CONF_LONGITUDE, hass.config.longitude)}"
        f"_{input_dict[CONF_FORECAST_TYPE]}"
    )


class ClimaCellOptionsConfigFlow(config_entries.OptionsFlow):
    """Handle ClimaCell options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize ClimaCell options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Manage the ClimaCell options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = {
            vol.Required(
                CONF_AQI_COUNTRY,
                default=self._config_entry.options.get(
                    CONF_AQI_COUNTRY, DEFAULT_AQI_COUNTRY
                ),
            ): vol.In((USA, CHINA)),
        }

        if self._config_entry.data[CONF_FORECAST_TYPE] == NOWCAST:
            options_schema.update(
                {
                    vol.Required(
                        CONF_TIMESTEP,
                        default=self._config_entry.options.get(
                            CONF_TIMESTEP, DEFAULT_TIMESTEP
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                }
            )

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options_schema),
        )


class ClimaCellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ClimaCell Weather API."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ClimaCellOptionsConfigFlow:
        """Get the options flow for this handler."""
        return ClimaCellOptionsConfigFlow(config_entry)

    async def async_step_user(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                unique_id=_get_unique_id(self.hass, user_input), raise_on_progress=True
            )
            self._abort_if_unique_id_configured()

            try:
                await ClimaCell(
                    user_input[CONF_API_KEY],
                    str(user_input.get(CONF_LATITUDE, self.hass.config.latitude)),
                    str(user_input.get(CONF_LONGITUDE, self.hass.config.longitude)),
                    session=async_get_clientsession(self.hass),
                ).realtime(ClimaCell.first_field(REALTIME))

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            except CantConnectException:
                errors["base"] = "cannot_connect"
            except InvalidAPIKeyException:
                errors[CONF_API_KEY] = "invalid_api_key"
            except RateLimitedException:
                errors[CONF_API_KEY] = "rate_limited"
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
            if entry.unique_id == _get_unique_id(self.hass, import_config):
                updated_data = {}
                updated_options = {}

                keys = entry.data.keys()
                for key in keys:
                    if key in import_config and entry.data[key] != import_config[key]:
                        updated_data[key] = import_config[key]

                for key in (CONF_TIMESTEP, CONF_AQI_COUNTRY):
                    if import_config[key] != entry.data[key]:
                        updated_options.update({key: import_config[key]})

                if updated_data or updated_options:
                    new_data = entry.data.copy()
                    new_data.update(updated_data)
                    new_options = entry.options.copy()
                    new_options.update(updated_options)
                    self.hass.config_entries.async_update_entry(
                        entry=entry, data=new_data, options=new_options
                    )
                    return self.async_abort(reason="updated_entry")

                return self.async_abort(reason="already_configured_account")

        return await self.async_step_user(user_input=import_config)
