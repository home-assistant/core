"""Config flow for InfluxDB integration."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from . import DOMAIN, create_influx_url, get_influx_connection
from .const import (
    CONF_API_VERSION,
    CONF_BUCKET,
    CONF_DB_NAME,
    CONF_ORG,
    CONF_SSL_CA_CERT,
    DEFAULT_API_VERSION,
)

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


class InfluxDBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for InfluxDB."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle the initial step."""
        host = import_data.get(CONF_HOST)
        database = import_data.get(CONF_DB_NAME)
        bucket = import_data.get(CONF_BUCKET)

        api_version = import_data.get(CONF_API_VERSION)
        ssl = import_data.get(CONF_SSL)

        if api_version == DEFAULT_API_VERSION:
            title = f"{database} ({host})"
            data = {
                CONF_API_VERSION: api_version,
                CONF_HOST: host,
                CONF_PORT: import_data.get(CONF_PORT),
                CONF_USERNAME: import_data.get(CONF_USERNAME),
                CONF_PASSWORD: import_data.get(CONF_PASSWORD),
                CONF_DB_NAME: database,
                CONF_SSL: ssl,
                CONF_PATH: import_data.get(CONF_PATH),
                CONF_VERIFY_SSL: import_data.get(CONF_VERIFY_SSL),
                CONF_SSL_CA_CERT: import_data.get(CONF_SSL_CA_CERT),
            }
        else:
            url = create_influx_url(import_data)
            title = f"{bucket} ({host})"
            data = {
                CONF_API_VERSION: api_version,
                CONF_URL: url,
                CONF_TOKEN: import_data.get(CONF_TOKEN),
                CONF_ORG: import_data.get(CONF_ORG),
                CONF_BUCKET: bucket,
                CONF_VERIFY_SSL: import_data.get(CONF_VERIFY_SSL),
                CONF_SSL_CA_CERT: import_data.get(CONF_SSL_CA_CERT),
            }

        errors = await _validate_influxdb_connection(self.hass, data)
        if errors:
            return self.async_abort(reason=errors["base"])

        return self.async_create_entry(title=title, data=data)
