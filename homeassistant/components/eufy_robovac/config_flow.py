"""Config flow for Eufy RoboVac."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .cloud_api import (
    CloudDiscoveredRoboVac,
    EufyRoboVacCloudApi,
    EufyRoboVacCloudApiError,
    EufyRoboVacCloudApiInvalidAuth,
)
from .const import (
    CONF_LOCAL_KEY,
    CONF_PROTOCOL_VERSION,
    DEFAULT_PROTOCOL_VERSION,
    DOMAIN,
)
from .local_api import EufyRoboVacLocalApi, EufyRoboVacLocalApiError
from .model_mappings import MODEL_MAPPINGS

_LOGGER = logging.getLogger(__name__)

SUPPORTED_PROTOCOL_VERSIONS = ("3.3", "3.4", "3.5")
CONF_SELECTED_DEVICE_ID = "selected_device_id"


def _user_step_data_schema(user_input: dict[str, str] | None = None) -> vol.Schema:
    """Return the schema for the account login step."""
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD): str,
        }
    )


def _device_step_data_schema(
    device: CloudDiscoveredRoboVac, user_input: dict[str, str] | None = None
) -> vol.Schema:
    """Return the schema for configuring a discovered RoboVac."""
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                default=user_input.get(CONF_HOST, device.host),
            ): str,
            vol.Optional(
                CONF_PROTOCOL_VERSION,
                default=user_input.get(
                    CONF_PROTOCOL_VERSION, device.protocol_version or DEFAULT_PROTOCOL_VERSION
                ),
            ): vol.In(SUPPORTED_PROTOCOL_VERSIONS),
        }
    )


USER_STEP_DATA_SCHEMA = _user_step_data_schema()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class NoDevicesFound(HomeAssistantError):
    """Error to indicate no RoboVacs were found."""


async def _async_validate_local_connection(
    hass: HomeAssistant,
    *,
    host: str,
    device_id: str,
    local_key: str,
    protocol_version: str,
) -> None:
    """Validate local connectivity for discovered RoboVac values."""
    api = EufyRoboVacLocalApi(
        host=host,
        device_id=device_id,
        local_key=local_key,
        protocol_version=protocol_version,
    )
    try:
        dps = await api.async_get_dps(hass)
    except EufyRoboVacLocalApiError as err:
        raise CannotConnect from err

    if not dps:
        raise CannotConnect


class EufyRoboVacConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eufy RoboVac."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._cloud_devices: dict[str, CloudDiscoveredRoboVac] = {}
        self._selected_device_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle account login and cloud discovery step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=USER_STEP_DATA_SCHEMA,
            )

        errors: dict[str, str] = {}
        username = user_input[CONF_USERNAME].strip()
        password = user_input[CONF_PASSWORD]
        user_input = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
        }

        try:
            discovered = await EufyRoboVacCloudApi(
                username=username,
                password=password,
            ).async_list_robovacs(self.hass)
            self._cloud_devices = {
                device.device_id: device
                for device in discovered
                if device.model in MODEL_MAPPINGS
            }
            if not self._cloud_devices:
                raise NoDevicesFound
        except EufyRoboVacCloudApiInvalidAuth:
            errors["base"] = "invalid_auth"
        except NoDevicesFound:
            errors["base"] = "no_devices"
        except EufyRoboVacCloudApiError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected exception discovering Eufy RoboVacs")
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=_user_step_data_schema(user_input),
                errors=errors,
            )

        return await self.async_step_select_device()

    async def async_step_select_device(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle RoboVac selection from cloud-discovered devices."""
        if not self._cloud_devices:
            return self.async_show_form(
                step_id="user",
                data_schema=USER_STEP_DATA_SCHEMA,
                errors={"base": "no_devices"},
            )

        if user_input is None:
            options = {
                device_id: f"{device.name} ({device.model})"
                for device_id, device in self._cloud_devices.items()
            }
            return self.async_show_form(
                step_id="select_device",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_SELECTED_DEVICE_ID): vol.In(options),
                    }
                ),
            )

        self._selected_device_id = user_input[CONF_SELECTED_DEVICE_ID]
        return await self.async_step_device()

    async def async_step_device(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle local details and entry creation for selected RoboVac."""
        if self._selected_device_id is None:
            return await self.async_step_select_device()

        selected = self._cloud_devices.get(self._selected_device_id)
        if selected is None:
            self._selected_device_id = None
            return await self.async_step_select_device()

        if user_input is None:
            return self.async_show_form(
                step_id="device",
                data_schema=_device_step_data_schema(selected),
            )

        errors: dict[str, str] = {}
        user_input = {
            **user_input,
            CONF_HOST: user_input[CONF_HOST].strip(),
        }

        if not user_input[CONF_HOST]:
            errors["base"] = "host_required"
        else:
            try:
                await _async_validate_local_connection(
                    self.hass,
                    host=user_input[CONF_HOST],
                    device_id=selected.device_id,
                    local_key=selected.local_key,
                    protocol_version=user_input.get(
                        CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION
                    ),
                )
            except CannotConnect:
                errors["base"] = "cannot_connect_local"
            except Exception:  # noqa: BLE001
                _LOGGER.exception(
                    "Unexpected exception validating local RoboVac connectivity"
                )
                errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="device",
                data_schema=_device_step_data_schema(selected, user_input),
                errors=errors,
            )

        entry_title = selected.name or selected.device_id
        entry_data = {
            CONF_NAME: entry_title,
            CONF_MODEL: selected.model,
            CONF_HOST: user_input[CONF_HOST],
            CONF_ID: selected.device_id,
            CONF_LOCAL_KEY: selected.local_key,
            CONF_PROTOCOL_VERSION: user_input.get(
                CONF_PROTOCOL_VERSION,
                DEFAULT_PROTOCOL_VERSION,
            ),
        }

        await self.async_set_unique_id(selected.device_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=entry_title,
            data=entry_data,
        )
