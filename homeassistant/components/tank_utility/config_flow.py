"""Config flow for Tank Utility integration."""

from functools import partial
from typing import Any, override

import probatio
import requests
from tank_utility import auth, device as tank_monitor

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICES, CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN, LOGGER


def _get_devices(email: str, password: str) -> list[str]:
    """Validate credentials and return the account's device IDs."""
    token = auth.get_token(email, password, force=True)
    return tank_monitor.get_devices(token)


class TankUtilityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tank Utility."""

    VERSION = 1

    async def _async_validate_input(
        self, email: str, password: str, devices: list[str] | None = None
    ) -> tuple[list[str] | None, str | None]:
        """Validate credentials and return (devices, error)."""
        try:
            if devices is None:
                devices = await self.hass.async_add_executor_job(
                    _get_devices, email, password
                )
            else:
                await self.hass.async_add_executor_job(
                    partial(auth.get_token, email, password, force=True)
                )
        except requests.exceptions.HTTPError as err:
            if (
                err.response is not None
                and err.response.status_code == requests.codes.unauthorized
            ):
                return None, "invalid_auth"
            return None, "cannot_connect"
        except requests.exceptions.RequestException:
            return None, "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return None, "unknown"
        return devices, None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            password = user_input[CONF_PASSWORD]
            self._async_abort_entries_match({CONF_EMAIL: email})

            devices, error = await self._async_validate_input(email, password)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_DEVICES: devices,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_EMAIL): str,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        email = import_data[CONF_EMAIL].strip().lower()
        password = import_data[CONF_PASSWORD]
        self._async_abort_entries_match({CONF_EMAIL: email})

        devices, error = await self._async_validate_input(
            email, password, import_data[CONF_DEVICES]
        )
        if error:
            return self.async_abort(reason=error)

        return self.async_create_entry(
            title=email,
            data={
                CONF_EMAIL: email,
                CONF_PASSWORD: password,
                CONF_DEVICES: devices,
            },
        )
