"""Config flow for the Kiosker integration."""

from __future__ import annotations

from collections.abc import Mapping
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
    CONF_POLL_INTERVAL,
    CONF_SSL,
    CONF_SSL_VERIFY,
    DEFAULT_POLL_INTERVAL,
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
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): int,
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
    except Exception as exc:
        _LOGGER.error("Failed to connect to Kiosker: %s", exc)
        raise CannotConnect from exc

    # Return info that you want to store in the config entry
    device_id = status.device_id if hasattr(status, "device_id") else data[CONF_HOST]
    return {"title": f"Kiosker {device_id}"}


class ConfigFlow(HAConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kiosker."""

    VERSION = 1
    MINOR_VERSION = 1
    CONNECTION_CLASS = "local_polling"

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
            except Exception:
                _LOGGER.exception("Unexpected exception")
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
                except Exception:  # noqa: BLE001
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
        if user_input is not None:
            # User confirmed, proceed to get API token
            return await self.async_step_discovery_confirm()

        # Show confirmation form with the stored title placeholders
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Use stored discovery info
            host = self._discovered_host
            port = self._discovered_port

            # Create config with discovered host/port and user-provided token
            config_data = {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                CONF_POLL_INTERVAL: user_input.get(
                    CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                ),
                CONF_SSL: user_input.get(CONF_SSL, DEFAULT_SSL),
                CONF_SSL_VERIFY: user_input.get(CONF_SSL_VERIFY, DEFAULT_SSL_VERIFY),
            }

            try:
                info = await validate_input(self.hass, config_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during discovery validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=config_data)

        # Show form to get API token for discovered device
        discovery_schema = vol.Schema(
            {
                vol.Required(CONF_API_TOKEN): str,
                vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): int,
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
                vol.Optional(CONF_SSL_VERIFY, default=DEFAULT_SSL_VERIFY): bool,
            }
        )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=discovery_schema,
            description_placeholders=self.context["title_placeholders"],
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            )

        # Get the config entry that's being re-authenticated
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="reauth_failed")

        # Create new config data with updated token
        new_data = entry.data.copy()
        new_data[CONF_API_TOKEN] = user_input[CONF_API_TOKEN]

        # Validate the new token
        try:
            await validate_input(self.hass, new_data)
        except CannotConnect:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
                errors={"base": "invalid_auth"},
            )
        except Exception:
            _LOGGER.exception("Unexpected exception during reauth")
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
                errors={"base": "unknown"},
            )

        # Update the config entry with new token
        self.hass.config_entries.async_update_entry(entry, data=new_data)
        await self.hass.config_entries.async_reload(entry.entry_id)

        return self.async_abort(reason="reauth_successful")


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
