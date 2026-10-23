"""Config flow for Tank Utility integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio
import requests
from tank_utility import auth

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICES, CONF_EMAIL, CONF_PASSWORD
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LOGGER


def _validate_credentials(email: str, password: str) -> None:
    """Validate credentials against Tank Utility API."""
    try:
        auth.get_token(email, password, force=True)
    except requests.exceptions.HTTPError as err:
        if (
            err.response is not None
            and err.response.status_code == requests.codes.unauthorized
        ):
            raise InvalidAuth from err
        raise CannotConnect from err
    except requests.exceptions.RequestException as err:
        raise CannotConnect from err


class TankUtilityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tank Utility."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()

            try:
                await self.hass.async_add_executor_job(
                    _validate_credentials, email, password
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with Tank Utility."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with Tank Utility."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            email = reauth_entry.data[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            try:
                await self.hass.async_add_executor_job(
                    _validate_credentials, email, password
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"email": reauth_entry.data[CONF_EMAIL]},
            data_schema=probatio.Schema(
                {
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        email = import_data[CONF_EMAIL].strip().lower()
        password = import_data[CONF_PASSWORD]
        pending_imports: dict[str, dict[str, Any]] = self.hass.data.setdefault(
            DOMAIN, {}
        )
        pending_entry = pending_imports.setdefault(
            email, {"devices": [], "passwords": [], "unrestricted": False}
        )
        if password not in pending_entry["passwords"]:
            pending_entry["passwords"].append(password)
        if (imported_devices := import_data.get(CONF_DEVICES)) is not None:
            pending_entry["devices"] = list(
                dict.fromkeys([*pending_entry["devices"], *imported_devices])
            )
        else:
            pending_entry["unrestricted"] = True

        existing_entry = await self.async_set_unique_id(email, raise_on_progress=False)
        if existing_entry is not None:
            pending_imports.pop(email, None)
            if CONF_DEVICES in existing_entry.data:
                if imported_devices is not None:
                    new_data = {
                        **existing_entry.data,
                        CONF_DEVICES: list(
                            dict.fromkeys(
                                [
                                    *existing_entry.data[CONF_DEVICES],
                                    *imported_devices,
                                ]
                            )
                        ),
                    }
                else:
                    new_data = {
                        k: v
                        for k, v in existing_entry.data.items()
                        if k != CONF_DEVICES
                    }
                if self.hass.config_entries.async_update_entry(
                    existing_entry, data=new_data
                ):
                    self.hass.config_entries.async_schedule_reload(
                        existing_entry.entry_id
                    )
            self._abort_if_unique_id_configured()
        if self._async_in_progress(
            include_uninitialized=True, match_context={"unique_id": email}
        ):
            return self.async_abort(reason="already_in_progress")

        try:
            passwords: list[str] = pending_entry["passwords"]
            idx = 0
            while True:
                candidate_password = passwords[idx]
                idx += 1
                try:
                    await self.hass.async_add_executor_job(
                        _validate_credentials, email, candidate_password
                    )
                except InvalidAuth:
                    if idx < len(passwords):
                        continue
                    return self.async_abort(reason="invalid_auth")
                except CannotConnect:
                    return self.async_abort(reason="cannot_connect")
                except Exception:  # noqa: BLE001
                    LOGGER.exception("Unexpected exception importing from YAML")
                    return self.async_abort(reason="unknown")
                password = candidate_password
                break
        finally:
            popped = pending_imports.pop(email, {})

        entry_data: dict[str, Any] = {
            CONF_EMAIL: email,
            CONF_PASSWORD: password,
        }
        if not popped.get("unrestricted"):
            entry_data[CONF_DEVICES] = popped["devices"]

        return self.async_create_entry(
            title=email,
            data=entry_data,
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotConnect(HomeAssistantError):
    """Error to indicate there is a connection error."""
