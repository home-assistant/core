"""Config flow for the Kiosker integration."""

from __future__ import annotations

import logging
from typing import Any

from kiosker import KioskerAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow as HAConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_API_TOKEN,
    CONF_SSL,
    CONF_SSL_VERIFY,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_SSL_VERIFY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_API_TOKEN): str,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
        vol.Optional(CONF_SSL_VERIFY, default=DEFAULT_SSL_VERIFY): bool,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = KioskerAPI(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        token=data[CONF_API_TOKEN],
        ssl=data[CONF_SSL],
        verify=data[CONF_SSL_VERIFY],
    )

    try:
        # Test connection by getting status
        status = await hass.async_add_executor_job(api.status)
    except (OSError, TimeoutError) as exc:
        _LOGGER.error("Failed to connect to Kiosker: %s", exc)
        raise CannotConnect from exc
    except Exception as exc:
        _LOGGER.error("Unexpected error connecting to Kiosker: %s", exc)
        raise CannotConnect from exc

    # Return info that you want to store in the config entry
    device_id = status.device_id if hasattr(status, "device_id") else data[CONF_HOST]
    # Use first 8 characters of device_id for consistency with entity naming
    display_id = device_id[:8] if len(device_id) > 8 else device_id
    return {"title": f"Kiosker {display_id}"}


class ConfigFlow(HAConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kiosker."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._discovered_host: str | None = None
        self._discovered_port: int | None = None
        self._discovered_uuid: str | None = None
        self._discovered_version: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except (ValueError, TypeError) as exc:
                _LOGGER.error("Invalid configuration data: %s", exc)
                errors["base"] = "invalid_host"
            except Exception:
                _LOGGER.exception("Unexpected exception during validation")
                errors["base"] = "unknown"
            else:
                # Get device info to determine unique ID
                api = KioskerAPI(
                    host=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                    token=user_input[CONF_API_TOKEN],
                    ssl=user_input[CONF_SSL],
                    verify=user_input[CONF_SSL_VERIFY],
                )
                try:
                    status = await self.hass.async_add_executor_job(api.status)
                    device_id = (
                        status.device_id
                        if hasattr(status, "device_id")
                        else f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                    )
                except (
                    OSError,
                    TimeoutError,
                    AttributeError,
                    ValueError,
                    TypeError,
                    KeyError,
                ) as exc:
                    _LOGGER.debug("Could not get device ID from status: %s", exc)
                    device_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                except Exception as exc:  # noqa: BLE001
                    # Broad exception in config flow for robustness during device discovery
                    _LOGGER.debug(
                        "Unexpected error getting device ID from status: %s", exc
                    )
                    device_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"

                # Use device ID as unique identifier
                await self.async_set_unique_id(device_id, raise_on_progress=False)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    }
                )

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT

        # Extract device information from zeroconf properties
        properties = discovery_info.properties
        uuid = properties.get("uuid")
        app_name = properties.get("app", "Kiosker")
        version = properties.get("version", "")

        # Use UUID from zeroconf if available, otherwise use host:port as fallback
        if uuid:
            device_name = f"{app_name} ({uuid[:8].upper()})"
            unique_id = uuid
        else:
            device_name = f"{app_name} {host}"
            unique_id = f"{host}:{port}"

        # Set unique ID and check for duplicates
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})

        # Store discovery info for confirmation step
        self.context["title_placeholders"] = {
            "name": device_name,
            "host": host,
            "port": str(port),
        }

        # Store discovered information for later use
        self._discovered_host = host
        self._discovered_port = port
        self._discovered_uuid = uuid
        self._discovered_version = version

        # Show confirmation dialog
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle zeroconf confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None and CONF_API_TOKEN in user_input:
            # Use stored discovery info and user-provided token
            host = self._discovered_host
            port = self._discovered_port

            # Create config with discovered host/port and user-provided token
            config_data = {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                CONF_SSL: user_input.get(CONF_SSL, DEFAULT_SSL),
                CONF_SSL_VERIFY: user_input.get(CONF_SSL_VERIFY, DEFAULT_SSL_VERIFY),
            }

            try:
                info = await validate_input(self.hass, config_data)
            except CannotConnect:
                errors[CONF_API_TOKEN] = "cannot_connect"
            except (ValueError, TypeError) as exc:
                _LOGGER.error("Invalid discovery data: %s", exc)
                errors[CONF_API_TOKEN] = "invalid_auth"
            except AttributeError as exc:
                _LOGGER.error("Invalid discovery data structure: %s", exc)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=config_data)

        # Show form to get API token for discovered device
        discovery_schema = vol.Schema(
            {
                vol.Required(CONF_API_TOKEN): str,
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
                vol.Optional(CONF_SSL_VERIFY, default=DEFAULT_SSL_VERIFY): bool,
            }
        )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=discovery_schema,
            description_placeholders=self.context["title_placeholders"],
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
