"""Config flow for Volkszaehler integration."""

import logging

from volkszaehler import Volkszaehler
from volkszaehler.exceptions import VolkszaehlerApiConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_FROM,
    CONF_SCANINTERVAL,
    CONF_TO,
    CONF_UUID,
    DEFAULT_HOST,
    DEFAULT_MONITORED_CONDITIONS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCANINTERVAL,
    DOMAIN,
    MIN_SCANINTERVAL,
    SENSOR_KEYS,
)

_LOGGER = logging.getLogger(__name__)


class VolkszaehlerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Volkszaehler integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_import(self, import_data) -> ConfigFlowResult:
        """Handle the import from YAML."""
        _LOGGER.info("Importing Volkszaehler entry with data: %s", import_data)

        uuid = import_data.get(CONF_UUID)
        if not uuid:
            _LOGGER.error("UUID is missing in import config")
            return self.async_abort(reason="missing_uuid")

        # Extrahiere Host und Port
        host = import_data.get(CONF_HOST, DEFAULT_HOST)
        port = import_data.get(CONF_PORT, DEFAULT_PORT)
        name = import_data.get(CONF_NAME, DEFAULT_NAME)

        # Extrahiere 'from' und 'to'
        param_from = import_data.get(CONF_FROM, "")
        param_to = import_data.get(CONF_TO, "")

        # Erstellen einer eindeutigen ID basierend auf UUID, Host, Port, From und To
        unique_id = f"{name}_{uuid}_{host}_{port}_{param_from}_{param_to}"

        # Setzen der eindeutigen ID, um Duplikate zu vermeiden
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Trennen von data und options
        data = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_UUID: uuid,
            CONF_NAME: import_data.get(CONF_NAME, "Volkszaehler"),
        }

        options = {
            CONF_SCANINTERVAL: import_data.get(CONF_SCANINTERVAL, DEFAULT_SCANINTERVAL),
            CONF_FROM: param_from,
            CONF_TO: param_to,
            CONF_MONITORED_CONDITIONS: import_data.get(
                CONF_MONITORED_CONDITIONS, [DEFAULT_MONITORED_CONDITIONS]
            ),
        }

        # Erstellen des ConfigEntries mit getrennten data und options
        return self.async_create_entry(
            title=name,
            data=data,
            options=options,  # Optionen getrennt übergeben
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial setup step by the user."""
        errors = {}

        if user_input is not None:
            # Eingabe validieren und die API-Verbindung testen
            scan_interval = user_input.get(CONF_SCANINTERVAL, DEFAULT_SCANINTERVAL)

            # Validate the polling interval
            if scan_interval < MIN_SCANINTERVAL:
                # errors["scan_interval"] = "too_low"
                errors["base"] = "too_low"

            try:
                await self._test_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_UUID],
                    user_input[CONF_FROM],
                    user_input[CONF_TO],
                )
                uuid = user_input[CONF_UUID]
                host = user_input.get(CONF_HOST, DEFAULT_HOST)
                port = user_input.get(CONF_PORT, DEFAULT_PORT)
                param_from = user_input.get(CONF_FROM, "")
                param_to = user_input.get(CONF_TO, "")
                unique_id = f"{uuid}@{host}:{port}@from:{param_from}@to:{param_to}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                data = {
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_UUID: uuid,
                    CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                }

                options = {
                    CONF_SCANINTERVAL: user_input.get(
                        CONF_SCANINTERVAL, DEFAULT_SCANINTERVAL
                    ),
                    CONF_FROM: param_from,
                    CONF_TO: param_to,
                    CONF_MONITORED_CONDITIONS: user_input.get(
                        CONF_MONITORED_CONDITIONS, ["average"]
                    ),
                }

                return self.async_create_entry(
                    title=data[CONF_NAME],
                    data=data,
                    options=options,
                )
            except VolkszaehlerApiConnectionError as e:
                _LOGGER.error("Connection error: %s", e)
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_UUID): str,
                vol.Optional(CONF_SCANINTERVAL, default=DEFAULT_SCANINTERVAL): int,
                vol.Optional(CONF_FROM, default=""): str,
                vol.Optional(CONF_TO, default=""): str,
                vol.Optional(
                    CONF_MONITORED_CONDITIONS, default=DEFAULT_MONITORED_CONDITIONS
                ): cv.multi_select(SENSOR_KEYS),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def _test_connection(self, host, port, uuid, param_from, param_to) -> None:
        """Test connection to the Volkszaehler API."""
        session = async_get_clientsession(self.hass)
        vz_api = Volkszaehler(
            session,
            uuid,
            host=host,
            port=port,
            param_from=param_from,
            param_to=param_to,
        )
        try:
            await vz_api.get_data()
            data = vz_api.data
        except VolkszaehlerApiConnectionError as err:
            raise ConnectionError(f"Error communicating with API: {err}") from err
        else:
            return data

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Volkszaehler."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options for the Volkszaehler integration."""
        if user_input is not None:
            # await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCANINTERVAL,
                    default=self._config_entry.options.get(
                        CONF_SCANINTERVAL, DEFAULT_SCANINTERVAL
                    ),
                ): int,
                vol.Optional(
                    CONF_FROM, default=self._config_entry.options.get(CONF_FROM, "")
                ): str,
                vol.Optional(
                    CONF_TO, default=self._config_entry.options.get(CONF_TO, "")
                ): str,
                vol.Optional(
                    CONF_MONITORED_CONDITIONS,
                    default=self._config_entry.options.get(
                        CONF_MONITORED_CONDITIONS, DEFAULT_MONITORED_CONDITIONS
                    ),
                ): cv.multi_select(SENSOR_KEYS),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
