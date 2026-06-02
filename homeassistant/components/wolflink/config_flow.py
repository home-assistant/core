"""Config flow for Wolf SmartSet Service integration."""

import logging
from typing import Any

from httpcore import ConnectError
import voluptuous as vol
from wolf_comm.models import Device
from wolf_comm.token_auth import InvalidAuth
from wolf_comm.wolf_client import WolfClient

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import DEVICE_ID, DOMAIN, SUBENTRY_TYPE_DEVICE

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def _fetch_systems(
    client: WolfClient,
) -> tuple[list[Device], dict[str, str]]:
    """Fetch the system list, returning ``(devices, errors)``."""
    errors: dict[str, str] = {}
    try:
        devices = await client.fetch_system_list()
    except ConnectError:
        errors["base"] = "cannot_connect"
    except InvalidAuth:
        errors["base"] = "invalid_auth"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    if errors:
        return [], errors
    return devices, errors


class WolfLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wolf SmartSet Service."""

    VERSION = 2
    MINOR_VERSION = 2

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_TYPE_DEVICE: DeviceSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step to get connection parameters."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            wolf_client = WolfClient(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            devices, errors = await _fetch_systems(wolf_client)
            if not errors:
                if not devices:
                    return self.async_abort(reason="no_devices")
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    subentries=[
                        ConfigSubentryData(
                            data={DEVICE_ID: device.id},
                            subentry_type=SUBENTRY_TYPE_DEVICE,
                            title=device.name,
                            unique_id=str(device.id),
                        )
                        for device in devices
                    ],
                )
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )


class DeviceSubentryFlow(ConfigSubentryFlow):
    """Subentry flow for adding a device that is no longer configured."""

    _fetched_systems: list[Device]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Fetch devices available on the account that are not yet configured."""
        entry = self._get_entry()
        wolf_client = WolfClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        devices, errors = await _fetch_systems(wolf_client)
        if errors:
            return self.async_abort(reason=errors["base"])

        configured_ids = {
            subentry.unique_id
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_DEVICE
        }
        self._fetched_systems = [
            device for device in devices if str(device.id) not in configured_ids
        ]
        if not self._fetched_systems:
            return self.async_abort(reason="no_devices_to_add")
        return await self.async_step_device()

    async def async_step_device(
        self, user_input: dict[str, str] | None = None
    ) -> SubentryFlowResult:
        """Allow user to pick a device to add."""
        if user_input is not None:
            device_id = int(user_input[DEVICE_ID])
            device = next(d for d in self._fetched_systems if d.id == device_id)
            return self.async_create_entry(
                title=device.name,
                data={DEVICE_ID: device.id},
                unique_id=str(device.id),
            )

        device_options = {
            str(device.id): device.name for device in self._fetched_systems
        }
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({vol.Required(DEVICE_ID): vol.In(device_options)}),
        )
