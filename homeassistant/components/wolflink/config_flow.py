"""Config flow for Wolf SmartSet Service integration."""

import logging

from httpcore import ConnectError
import voluptuous as vol
from wolf_comm.models import Device
from wolf_comm.token_auth import InvalidAuth
from wolf_comm.wolf_client import WolfClient

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import CONF_DEVICES, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class WolfLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wolf SmartSet Service."""

    VERSION = 2
    MINOR_VERSION = 1

    fetched_systems: list[Device]

    def __init__(self) -> None:
        """Initialize."""
        self.username: str | None = None
        self.password: str | None = None

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
                self.fetched_systems = await wolf_client.fetch_system_list()
            except ConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.username = user_input[CONF_USERNAME]
                self.password = user_input[CONF_PASSWORD]
                await self.async_set_unique_id(self.username.lower())
                self._abort_if_unique_id_configured()
                return await self.async_step_devices()
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_devices(
        self, user_input: dict[str, list[str]] | None = None
    ) -> ConfigFlowResult:
        """Allow user to select which devices to monitor."""
        device_map = {str(d.id): d.name for d in self.fetched_systems}
        if user_input is not None:
            assert self.username is not None
            assert self.password is not None
            return self.async_create_entry(
                title=self.username,
                data={
                    CONF_USERNAME: self.username,
                    CONF_PASSWORD: self.password,
                },
                options={
                    CONF_DEVICES: user_input[CONF_DEVICES],
                },
            )
        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICES, default=list(device_map)): cv.multi_select(
                    device_map
                ),
            }
        )
        return self.async_show_form(step_id="devices", data_schema=data_schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return WolfLinkOptionsFlow()


class WolfLinkOptionsFlow(OptionsFlowWithReload):
    """Handle Wolf SmartSet options."""

    async def async_step_init(
        self, user_input: dict[str, list[str]] | None = None
    ) -> ConfigFlowResult:
        """Manage Wolf SmartSet options."""
        errors: dict[str, str] = {}

        runtime_data = getattr(self.config_entry, "runtime_data", None)
        wolf_client: WolfClient | None = None
        if runtime_data is not None:
            wolf_client = getattr(runtime_data, "wolf_client", None)

        if wolf_client is None:
            username: str = self.config_entry.data[CONF_USERNAME]
            password: str = self.config_entry.data[CONF_PASSWORD]
            wolf_client = WolfClient(username, password)
        try:
            devices = await wolf_client.fetch_system_list()
        except ConnectError:
            errors["base"] = "cannot_connect"
            devices = []
        except InvalidAuth:
            errors["base"] = "invalid_auth"
            devices = []
        except Exception:
            _LOGGER.exception("Unexpected exception fetching device list")
            errors["base"] = "unknown"
            devices = []

        device_map = {str(d.id): d.name for d in devices}

        if user_input is not None and not errors:
            return self.async_create_entry(
                data={CONF_DEVICES: user_input[CONF_DEVICES]}
            )

        # Filter out stale IDs no longer on the account
        current_devices = [
            dev_id
            for dev_id in self.config_entry.options.get(CONF_DEVICES, list(device_map))
            if dev_id in device_map
        ]

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICES, default=current_devices): cv.multi_select(
                    device_map
                ),
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )
