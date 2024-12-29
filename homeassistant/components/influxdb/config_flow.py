"""Config flow for InfluxDB integration."""

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant

from . import DOMAIN, get_influx_connection

_LOGGER = logging.getLogger(__name__)


async def _validate_influxdb_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, str] | None:
    """Validate connection to influxdb."""

    try:
        influx = await hass.async_add_executor_job(get_influx_connection, data, True)
    except ConnectionError as ex:
        _LOGGER.error(ex)
        return {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unknown error")
        return {"base": "unknown"}

    influx.close()

    return None


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for InfluxDB."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, import_config=None) -> ConfigFlowResult:
        """Handle the initial step."""
        host = import_config.get("host")

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured(import_config)

        errors = await _validate_influxdb_connection(self.hass, import_config)
        if errors:
            return self.async_abort(reason=errors["base"])

        return self.async_create_entry(title=host, data=import_config)
