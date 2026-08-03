"""Config flow for Hikvision integration."""

import logging
from typing import Any, override

from pyhik.hikvision import HikCamera
import requests
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HikvisionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hikvision."""

    VERSION = 1
    MINOR_VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            ssl = user_input[CONF_SSL]
            verify_ssl = user_input[CONF_VERIFY_SSL]

            protocol = "https" if ssl else "http"
            url = f"{protocol}://{host}"

            try:
                camera = await self.hass.async_add_executor_job(
                    HikCamera, url, port, username, password, verify_ssl
                )
            except requests.exceptions.RequestException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                device_id = camera.get_id
                device_name = camera.get_name
                if device_id is None:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(device_id)

                    if self.source == SOURCE_RECONFIGURE:
                        self._abort_if_unique_id_mismatch()
                        entry = self._get_reconfigure_entry()
                        return self.async_update_reload_and_abort(
                            entry,
                            data_updates={
                                CONF_HOST: host,
                                CONF_PORT: port,
                                CONF_USERNAME: username,
                                CONF_PASSWORD: password,
                                CONF_SSL: ssl,
                                CONF_VERIFY_SSL: verify_ssl,
                            },
                        )

                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=device_name or host,
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                            CONF_SSL: ssl,
                            CONF_VERIFY_SSL: verify_ssl,
                        },
                    )

        if self.source == SOURCE_RECONFIGURE:
            # Set schema with suggested values.
            schema = vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_SSL, default=False): bool,
                    vol.Optional(CONF_VERIFY_SSL, default=True): bool,
                }
            )

            entry = self._get_reconfigure_entry()

            schema = self.add_suggested_values_to_schema(
                schema,
                {**entry.data, **(user_input or {})},
            )

            return self.async_show_form(
                step_id="user",
                data_schema=schema,
                errors=errors,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_SSL, default=False): bool,
                    vol.Optional(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: ConfigType) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        host = import_data[CONF_HOST]
        port = import_data.get(CONF_PORT, DEFAULT_PORT)
        username = import_data[CONF_USERNAME]
        password = import_data[CONF_PASSWORD]
        ssl = import_data.get(CONF_SSL, False)
        verify_ssl = import_data.get(CONF_VERIFY_SSL, True)
        name = import_data.get(CONF_NAME)

        protocol = "https" if ssl else "http"
        url = f"{protocol}://{host}"

        try:
            camera = await self.hass.async_add_executor_job(
                HikCamera, url, port, username, password, verify_ssl
            )
        except requests.exceptions.RequestException:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        device_id = camera.get_id
        device_name = camera.get_name
        if device_id is None:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=name or device_name or host,
            data={
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_SSL: ssl,
                CONF_VERIFY_SSL: verify_ssl,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device re-configuration."""
        return await self.async_step_user(None)
