"""Config flow for InfluxDB integration."""

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import DOMAIN, get_influx_connection
from .const import CONF_API_VERSION, CONF_BUCKET, CONF_DB_NAME, DEFAULT_API_VERSION

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
        host = import_config.get(CONF_HOST)
        database = import_config.get(CONF_DB_NAME)
        bucket = import_config.get(CONF_BUCKET)

        if import_config[CONF_API_VERSION] == DEFAULT_API_VERSION:
            unique_id = f"{host}_{database}"
            title = f"{database} ({host})"
        else:
            unique_id = f"{host}_{bucket}"
            title = f"{bucket} ({host})"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(import_config)

        errors = await _validate_influxdb_connection(self.hass, import_config)
        if errors:
            return self.async_abort(reason=errors["base"])

        return self.async_create_entry(title=title, data=import_config)
