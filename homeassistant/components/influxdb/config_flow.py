"""Config flow for InfluxDB integration."""

import logging
from pathlib import Path
import shutil
from typing import Any

import voluptuous as vol
from yarl import URL

from homeassistant.components.file_upload import process_uploaded_file
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
from homeassistant.helpers.selector import (
    FileSelector,
    FileSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.storage import STORAGE_DIR

from . import DOMAIN, get_influx_connection
from .const import (
    API_VERSION_2,
    CONF_API_VERSION,
    CONF_BUCKET,
    CONF_DB_NAME,
    CONF_ORG,
    CONF_SSL_CA_CERT,
    DEFAULT_API_VERSION,
    DEFAULT_HOST,
    DEFAULT_PORT,
)

_LOGGER = logging.getLogger(__name__)

INFLUXDB_V1_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_URL, default=f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
        ): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
                autocomplete="url",
            ),
        ),
        vol.Required(CONF_VERIFY_SSL, default=False): bool,
        vol.Required(CONF_DB_NAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
            ),
        ),
        vol.Optional(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        vol.Optional(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
        vol.Optional(CONF_SSL_CA_CERT): FileSelector(
            FileSelectorConfig(accept=".pem,.crt,.cer,.der")
        ),
    }
)

INFLUXDB_V2_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="https://"): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
                autocomplete="url",
            ),
        ),
        vol.Required(CONF_VERIFY_SSL, default=False): bool,
        vol.Required(CONF_ORG): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
            ),
        ),
        vol.Required(CONF_BUCKET): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
            ),
        ),
        vol.Required(CONF_TOKEN): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
            ),
        ),
        vol.Optional(CONF_SSL_CA_CERT): FileSelector(
            FileSelectorConfig(accept=".pem,.crt,.cer,.der")
        ),
    }
)


async def _validate_influxdb_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate connection to influxdb."""

    def _test_connection() -> None:
        influx = get_influx_connection(data, test_write=True)
        influx.close()

    errors = {}

    try:
        await hass.async_add_executor_job(_test_connection)
    except ConnectionError as ex:
        _LOGGER.error(ex)
        if "SSLError" in ex.args[0]:
            errors = {"base": "ssl_error"}
        elif "database not found" in ex.args[0]:
            errors = {"base": "invalid_database"}
        elif "authorization failed" in ex.args[0]:
            errors = {"base": "invalid_auth"}
        elif "token" in ex.args[0]:
            errors = {"base": "invalid_config"}
        else:
            errors = {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unknown error")
        errors = {"base": "unknown"}

    return errors


async def _save_uploaded_cert_file(hass: HomeAssistant, uploaded_file_id: str) -> Path:
    """Move the uploaded file to storage directory."""

    def _process_upload() -> Path:
        with process_uploaded_file(hass, uploaded_file_id) as file_path:
            dest_path = Path(hass.config.path(STORAGE_DIR, DOMAIN))
            dest_path.mkdir(exist_ok=True)
            file_name = f"influxdb{file_path.suffix}"
            dest_file = dest_path / file_name
            shutil.move(file_path, dest_file)
        return dest_file

    return await hass.async_add_executor_job(_process_upload)


class InfluxDBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for InfluxDB."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes an integration."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["configure_v1", "configure_v2"],
        )

    async def async_step_configure_v1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user configures InfluxDB v1."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = URL(user_input[CONF_URL])
            data = {
                CONF_API_VERSION: DEFAULT_API_VERSION,
                CONF_HOST: url.host,
                CONF_PORT: url.port,
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                CONF_DB_NAME: user_input[CONF_DB_NAME],
                CONF_SSL: url.scheme == "https",
                CONF_PATH: url.path,
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
            }
            if (cert := user_input.get(CONF_SSL_CA_CERT)) is not None:
                path = await _save_uploaded_cert_file(self.hass, cert)
                data[CONF_SSL_CA_CERT] = str(path)
            errors = await _validate_influxdb_connection(self.hass, data)

            if not errors:
                title = f"{data[CONF_DB_NAME]} ({data[CONF_HOST]})"
                return self.async_create_entry(title=title, data=data)

        schema = INFLUXDB_V1_SCHEMA

        return self.async_show_form(
            step_id="configure_v1",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_configure_v2(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user configures InfluxDB v2."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                CONF_API_VERSION: API_VERSION_2,
                CONF_URL: user_input[CONF_URL],
                CONF_TOKEN: user_input[CONF_TOKEN],
                CONF_ORG: user_input[CONF_ORG],
                CONF_BUCKET: user_input[CONF_BUCKET],
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
            }
            if (cert := user_input.get(CONF_SSL_CA_CERT)) is not None:
                path = await _save_uploaded_cert_file(self.hass, cert)
                data[CONF_SSL_CA_CERT] = str(path)
            errors = await _validate_influxdb_connection(self.hass, data)

            if not errors:
                title = f"{data[CONF_BUCKET]} ({data[CONF_URL]})"
                return self.async_create_entry(title=title, data=data)

        schema = INFLUXDB_V2_SCHEMA

        return self.async_show_form(
            step_id="configure_v2",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

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
            url = import_data.get(CONF_URL)
            title = f"{bucket} ({url})"
            data = {
                CONF_API_VERSION: api_version,
                CONF_URL: import_data.get(CONF_URL),
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
