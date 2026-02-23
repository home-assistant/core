"""Config flow for the Teltonika integration."""

from __future__ import annotations

import logging
from typing import Any

from teltasync import Teltasync, TeltonikaAuthenticationError, TeltonikaConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN
from .util import get_url_variants

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
    }
)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    host = data[CONF_HOST]

    last_error: Exception | None = None

    for base_url in get_url_variants(host):
        client = Teltasync(
            base_url=f"{base_url}/api",
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            session=session,
            verify_ssl=data.get(CONF_VERIFY_SSL, True),
        )

        try:
            device_info = await client.get_device_info()
            auth_valid = await client.validate_credentials()
        except TeltonikaConnectionError as err:
            _LOGGER.debug(
                "Failed to connect to Teltonika device at %s: %s", base_url, err
            )
            last_error = err
            continue
        except TeltonikaAuthenticationError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise InvalidAuth from err
        finally:
            await client.close()

        if not auth_valid:
            raise InvalidAuth

        return {
            "title": device_info.device_name,
            "device_id": device_info.device_identifier,
            "host": base_url,
        }

    _LOGGER.error("Cannot connect to device after trying all schemas")
    raise CannotConnect from last_error


class TeltonikaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Teltonika."""

    VERSION = 1
    MINOR_VERSION = 1
    _discovered_host: str | None = None

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
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Set unique ID to prevent duplicates
                await self.async_set_unique_id(info["device_id"])
                self._abort_if_unique_id_configured()

                data_to_store = dict(user_input)
                if "host" in info:
                    data_to_store[CONF_HOST] = info["host"]

                return self.async_create_entry(
                    title=info["title"],
                    data=data_to_store,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        host = discovery_info.ip

        # Store discovered host for later use
        self._discovered_host = host

        # Try to get device info without authentication to get device identifier and name
        session = async_get_clientsession(self.hass)

        for base_url in get_url_variants(host):
            client = Teltasync(
                base_url=f"{base_url}/api",
                username="",  # No credentials yet
                password="",
                session=session,
                verify_ssl=False,  # Teltonika devices use self-signed certs by default
            )

            try:
                # Get device info from unauthorized endpoint
                device_info = await client.get_device_info()
                device_name = device_info.device_name
                device_id = device_info.device_identifier
                break
            except TeltonikaConnectionError:
                # Connection failed, try next URL variant
                continue
            finally:
                await client.close()
        else:
            # No URL variant worked, device not reachable, don't autodiscover
            return self.async_abort(reason="cannot_connect")

        # Set unique ID and check for existing conf
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Store discovery info for the user step
        self.context["title_placeholders"] = {
            "name": device_name,
            "host": host,
        }

        # Proceed to confirmation step to get credentials
        return await self.async_step_dhcp_confirm()

    async def async_step_dhcp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm DHCP discovery and get credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Get the host from the discovery
            host = getattr(self, "_discovered_host", "")

            try:
                # Validate credentials with discovered host
                data = {
                    CONF_HOST: host,
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_VERIFY_SSL: False,
                }
                info = await validate_input(self.hass, data)

                # Update unique ID to device identifier if we didn't get it during discovery
                await self.async_set_unique_id(
                    info["device_id"], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: info["host"],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_VERIFY_SSL: False,
                    },
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during DHCP confirm")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="dhcp_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders=self.context.get("title_placeholders", {}),
        )
