"""Config flow for InfluxDB integration."""

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
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
from homeassistant.data_entry_flow import AbortFlow

from . import DOMAIN, get_influx_connection
from .const import (
    CONF_API_VERSION,
    CONF_BUCKET,
    CONF_COMPONENT_CONFIG,
    CONF_COMPONENT_CONFIG_DOMAIN,
    CONF_COMPONENT_CONFIG_GLOB,
    CONF_DB_NAME,
    CONF_DEFAULT_MEASUREMENT,
    CONF_IGNORE_ATTRIBUTES,
    CONF_MEASUREMENT_ATTR,
    CONF_ORG,
    CONF_OVERRIDE_MEASUREMENT,
    CONF_PRECISION,
    CONF_RETRY_COUNT,
    CONF_SSL_CA_CERT,
    CONF_TAGS,
    CONF_TAGS_ATTRIBUTES,
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


class InfluxDBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for InfluxDB."""

    VERSION = 1

    async def _abort_if_host_database_configured(
        self,
        data: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        """Test if host and database are already configured."""
        host = data.get(CONF_HOST)
        database = data.get(CONF_DB_NAME)
        bucket = data.get(CONF_BUCKET)

        for entry in self._async_current_entries():
            if (
                entry.data[CONF_API_VERSION] == DEFAULT_API_VERSION
                and entry.data[CONF_HOST] == host
                and entry.data.get(CONF_DB_NAME) == database
            ) or (
                entry.data[CONF_API_VERSION] != DEFAULT_API_VERSION
                and entry.data[CONF_HOST] == host
                and entry.data.get(CONF_BUCKET) == bucket
            ):
                if data is not None and options is not None:
                    changed = self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, **data},
                        options={**entry.options, **options},
                    )
                    if changed and entry.state in (
                        config_entries.ConfigEntryState.LOADED,
                        config_entries.ConfigEntryState.SETUP_RETRY,
                    ):
                        self.hass.async_create_task(
                            self.hass.config_entries.async_reload(entry.entry_id)
                        )
                raise AbortFlow("already_configured")

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle the initial step."""
        host = import_data.get(CONF_HOST)
        database = import_data.get(CONF_DB_NAME)
        bucket = import_data.get(CONF_BUCKET)

        data = {
            CONF_API_VERSION: import_data.get(CONF_API_VERSION),
            CONF_HOST: import_data.get(CONF_HOST),
            CONF_PORT: import_data.get(CONF_PORT),
            CONF_USERNAME: import_data.get(CONF_USERNAME),
            CONF_PASSWORD: import_data.get(CONF_PASSWORD),
            CONF_DB_NAME: import_data.get(CONF_DB_NAME),
            CONF_TOKEN: import_data.get(CONF_TOKEN),
            CONF_ORG: import_data.get(CONF_ORG),
            CONF_BUCKET: import_data.get(CONF_BUCKET),
            CONF_URL: import_data.get(CONF_URL),
            CONF_SSL: import_data.get(CONF_SSL),
            CONF_PATH: import_data.get(CONF_PATH),
            CONF_VERIFY_SSL: import_data.get(CONF_VERIFY_SSL),
            CONF_SSL_CA_CERT: import_data.get(CONF_SSL_CA_CERT),
        }

        options = {
            CONF_RETRY_COUNT: import_data.get(CONF_RETRY_COUNT),
            CONF_PRECISION: import_data.get(CONF_PRECISION),
            CONF_MEASUREMENT_ATTR: import_data.get(CONF_MEASUREMENT_ATTR),
            CONF_DEFAULT_MEASUREMENT: import_data.get(CONF_DEFAULT_MEASUREMENT),
            CONF_OVERRIDE_MEASUREMENT: import_data.get(CONF_OVERRIDE_MEASUREMENT),
            CONF_INCLUDE: import_data.get(CONF_INCLUDE),
            CONF_EXCLUDE: import_data.get(CONF_EXCLUDE),
            CONF_TAGS: import_data.get(CONF_TAGS),
            CONF_TAGS_ATTRIBUTES: import_data.get(CONF_TAGS_ATTRIBUTES),
            CONF_IGNORE_ATTRIBUTES: import_data.get(CONF_IGNORE_ATTRIBUTES),
            CONF_COMPONENT_CONFIG: import_data.get(CONF_COMPONENT_CONFIG),
            CONF_COMPONENT_CONFIG_DOMAIN: import_data.get(CONF_COMPONENT_CONFIG_DOMAIN),
            CONF_COMPONENT_CONFIG_GLOB: import_data.get(CONF_COMPONENT_CONFIG_GLOB),
        }

        if import_data[CONF_API_VERSION] == DEFAULT_API_VERSION:
            title = f"{database} ({host})"
        else:
            title = f"{bucket} ({host})"

        await self._abort_if_host_database_configured(data, options)

        errors = await _validate_influxdb_connection(self.hass, import_data)
        if errors:
            return self.async_abort(reason=errors["base"])

        return self.async_create_entry(title=title, data=data, options=options)
