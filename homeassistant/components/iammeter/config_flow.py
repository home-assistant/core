"""Config flow for IAMMETER."""

from datetime import timedelta
import logging
from typing import Any, override

from iammeter.client import normalize_connection
import probatio
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.helpers import config_validation as cv

from .const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import async_get_meter

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_SCHEMA = probatio.All(
    cv.positive_int, probatio.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
)

CONNECTION_SCHEMA = {
    probatio.Required(CONF_HOST): cv.string,
    probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
    probatio.Required(
        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
    ): SCAN_INTERVAL_SCHEMA,
}
STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME, default=DEFAULT_NAME): probatio.All(
            cv.string, probatio.Strip, probatio.Length(min=1)
        ),
        **CONNECTION_SCHEMA,
    }
)
STEP_RECONFIGURE_DATA_SCHEMA = probatio.Schema(CONNECTION_SCHEMA)


class IammeterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an IAMMETER config flow."""

    VERSION = 1

    async def _async_validate_input(self, data: dict[str, Any]) -> str | None:
        """Validate a connection and set the meter's unique ID."""
        try:
            data[CONF_HOST], data[CONF_PORT], _ = normalize_connection(
                data[CONF_HOST], data.get(CONF_PORT, DEFAULT_PORT)
            )
        except ValueError:
            return "invalid_host"
        try:
            api = await async_get_meter(self.hass, data)
        except ValueError:
            return "invalid_data"
        except RequestException, TimeoutError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error connecting to IAMMETER")
            return "unknown"
        await self.async_set_unique_id(api.measurement["sn"])
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow started by the user."""
        errors = {}
        if user_input is not None:
            if error := await self._async_validate_input(user_input):
                errors["base"] = error
            else:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                    options={
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        )
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a legacy YAML sensor platform."""
        data = {
            CONF_HOST: import_data[CONF_HOST],
            CONF_PORT: import_data.get(CONF_PORT, DEFAULT_PORT),
        }
        if error := await self._async_validate_input(data):
            return self.async_abort(reason=error)
        self._abort_if_unique_id_configured()
        interval = import_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        if isinstance(interval, timedelta):
            interval = interval.total_seconds()
        try:
            interval = SCAN_INTERVAL_SCHEMA(interval)
        except probatio.Invalid:
            return self.async_abort(reason="invalid_interval")
        return self.async_create_entry(
            title=import_data.get(CONF_NAME, DEFAULT_NAME),
            data=data,
            options={CONF_SCAN_INTERVAL: interval},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the connection to the same meter."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            if error := await self._async_validate_input(user_input):
                errors["base"] = error
            else:
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                    options={
                        **entry.options,
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    },
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_DATA_SCHEMA,
                user_input
                or {
                    **entry.data,
                    CONF_SCAN_INTERVAL: entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                },
            ),
            errors=errors,
        )
