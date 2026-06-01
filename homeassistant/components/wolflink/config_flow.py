"""Config flow for Wolf SmartSet Service integration."""

import logging

from httpcore import ConnectError
import voluptuous as vol
from wolf_comm.models import Device
from wolf_comm.token_auth import InvalidAuth
from wolf_comm.wolf_client import WolfClient

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv

from .const import DEVICE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class WolfLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wolf SmartSet Service."""

    VERSION = 2
    MINOR_VERSION = 1

    _fetched_systems: list[Device]
    _username: str
    _password: str

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step to get connection parameters."""
        errors: dict[str, str] = {}
        if user_input is not None:
            wolf_client = WolfClient(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            try:
                self._fetched_systems = await wolf_client.fetch_system_list()
            except ConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._username = user_input[CONF_USERNAME]
                self._password = user_input[CONF_PASSWORD]
                return await self.async_step_device()
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_device(
        self, user_input: dict[str, list[str]] | None = None
    ) -> ConfigFlowResult:
        """Allow user to select devices to add."""
        if user_input is not None:
            selected_ids = user_input[DEVICE_ID]
            await self.async_set_unique_id(self._username.lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._username,
                data={
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    DEVICE_ID: [int(did) for did in selected_ids],
                },
            )

        device_options = {
            str(device.id): device.name for device in self._fetched_systems
        }
        data_schema = vol.Schema(
            {
                vol.Required(DEVICE_ID): vol.All(
                    cv.multi_select(device_options),
                    vol.Length(min=1),
                )
            }
        )
        return self.async_show_form(step_id="device", data_schema=data_schema)

    async def async_step_reconfigure(
        self, user_input: dict[str, list[str]] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration to change selected devices."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_ids = user_input[DEVICE_ID]
            return self.async_update_reload_and_abort(
                entry,
                data={
                    **entry.data,
                    DEVICE_ID: [int(did) for did in selected_ids],
                },
            )

        wolf_client = WolfClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        try:
            self._fetched_systems = await wolf_client.fetch_system_list()
        except ConnectError:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if errors:
            return self.async_abort(reason=next(iter(errors.values())))

        current_ids = entry.data.get(DEVICE_ID, [])
        device_options = {
            str(device.id): device.name for device in self._fetched_systems
        }
        data_schema = vol.Schema(
            {
                vol.Required(
                    DEVICE_ID, default=[str(did) for did in current_ids]
                ): vol.All(
                    cv.multi_select(device_options),
                    vol.Length(min=1),
                )
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=data_schema, errors=errors
        )
