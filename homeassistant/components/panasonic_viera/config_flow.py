"""Config flow for Panasonic Viera TV integration."""

from functools import partial
import logging
from typing import Any
from urllib.error import URLError

from panasonic_viera import TV_TYPE_ENCRYPTED, RemoteControl, SOAPError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_PORT

from .const import (
    ATTR_DEVICE_INFO,
    ATTR_FRIENDLY_NAME,
    ATTR_UDN,
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
    CONF_ON_ACTION,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    ERROR_INVALID_PIN_CODE,
)

_LOGGER = logging.getLogger(__name__)


class PanasonicVieraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Panasonic Viera."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Panasonic Viera config flow."""
        self._data: dict[str, Any] = {
            CONF_HOST: None,
            CONF_NAME: None,
            CONF_PORT: None,
            CONF_ON_ACTION: None,
            ATTR_DEVICE_INFO: None,
        }

        self._remote: RemoteControl | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_load_data(user_input)
            try:
                self._remote = await self.hass.async_add_executor_job(
                    partial(RemoteControl, self._data[CONF_HOST], self._data[CONF_PORT])
                )
                assert self._remote is not None
                self._data[ATTR_DEVICE_INFO] = await self.hass.async_add_executor_job(
                    self._remote.get_device_info
                )
            except (URLError, SOAPError, OSError) as err:
                _LOGGER.error("Could not establish remote connection: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("An unknown error occurred")
                return self.async_abort(reason="unknown")
            else:
                await self.async_set_unique_id(self._data[ATTR_DEVICE_INFO][ATTR_UDN])
                self._abort_if_unique_id_configured()

                if self._data[CONF_NAME] == DEFAULT_NAME:
                    self._data[CONF_NAME] = self._data[ATTR_DEVICE_INFO][
                        ATTR_FRIENDLY_NAME
                    ].replace("_", " ")

                if self._remote.type == TV_TYPE_ENCRYPTED:
                    return await self.async_step_pairing()

                return self.async_create_entry(
                    title=self._data[CONF_NAME],
                    data=self._data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=self._data[CONF_HOST]
                        if self._data[CONF_HOST] is not None
                        else "",
                    ): str,
                    vol.Optional(
                        CONF_NAME,
                        default=self._data[CONF_NAME]
                        if self._data[CONF_NAME] is not None
                        else DEFAULT_NAME,
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_pairing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pairing step."""
        errors: dict[str, str] = {}
        assert self._remote is not None

        if user_input is not None:
            pin = user_input[CONF_PIN]
            try:
                await self.hass.async_add_executor_job(
                    partial(self._remote.authorize_pin_code, pincode=pin)
                )
            except SOAPError as err:
                _LOGGER.error("Invalid PIN code: %s", err)
                errors["base"] = ERROR_INVALID_PIN_CODE
            except (URLError, OSError) as err:
                _LOGGER.error("The remote connection was lost: %s", err)
                return self.async_abort(reason="cannot_connect")
            except Exception:
                _LOGGER.exception("Unknown error")
                return self.async_abort(reason="unknown")

            if "base" not in errors:
                encryption_data = {
                    CONF_APP_ID: self._remote.app_id,
                    CONF_ENCRYPTION_KEY: self._remote.enc_key,
                }

                self._data = {**self._data, **encryption_data}

                return self.async_create_entry(
                    title=self._data[CONF_NAME],
                    data=self._data,
                )

        try:
            await self.hass.async_add_executor_job(
                partial(self._remote.request_pin_code, name="Home Assistant")
            )
        except (URLError, SOAPError, OSError) as err:
            _LOGGER.error("The remote connection was lost: %s", err)
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unknown error")
            return self.async_abort(reason="unknown")

        return self.async_show_form(
            step_id="pairing",
            data_schema=vol.Schema({vol.Required(CONF_PIN): str}),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(user_input=import_data)

    async def async_load_data(self, config: dict[str, Any]) -> None:
        """Load the data."""
        self._data = config

        self._data[CONF_PORT] = self._data.get(CONF_PORT, DEFAULT_PORT)
        self._data[CONF_ON_ACTION] = self._data.get(CONF_ON_ACTION)

        await self.async_set_unique_id(self._data[CONF_HOST])
        self._abort_if_unique_id_configured()
