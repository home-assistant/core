"""Config flow for the Teltonika integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from teltasync import Teltasync, TeltonikaAuthenticationError, TeltonikaConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_VALIDATE_SSL, DOMAIN
from .util import base_url_to_host, candidate_base_urls

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_VALIDATE_SSL, default=False): bool,
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

    for base_url in candidate_base_urls(host):
        client = Teltasync(
            base_url=base_url,
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            session=session,
            verify_ssl=data.get(CONF_VALIDATE_SSL, True),
        )

        try:
            device_info = await client.get_device_info()
            auth_valid = await client.validate_credentials()
            if not auth_valid:
                raise InvalidAuth

            return {
                "title": getattr(device_info, "device_name", host),
                "serial": getattr(device_info, "device_identifier", None),
                "host": base_url_to_host(base_url),
            }
        except TeltonikaConnectionError as err:
            _LOGGER.debug(
                "Failed to connect to Teltonika device at %s: %s", base_url, err
            )
            last_error = err
        except TeltonikaAuthenticationError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise InvalidAuth from err
        finally:
            await client.close()

    _LOGGER.error("Cannot connect to device after trying all protocols")
    if last_error is not None:
        raise CannotConnect from last_error
    raise CannotConnect


class TeltonikaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Teltonika."""

    VERSION = 1
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
                await self.async_set_unique_id(info["serial"] or info["title"])
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth when authentication fails."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                # Validate new credentials and host
                data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_VALIDATE_SSL: reauth_entry.data.get(CONF_VALIDATE_SSL, False),
                }
                info = await validate_input(self.hass, data)

                # Verify it's the same device
                if info["serial"] and reauth_entry.unique_id != info["serial"]:
                    return self.async_abort(reason="wrong_account")

                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_HOST: info["host"],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=reauth_entry.data[CONF_HOST]): str,
                    vol.Required(
                        CONF_USERNAME, default=reauth_entry.data[CONF_USERNAME]
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "name": reauth_entry.title,
                "host": reauth_entry.data[CONF_HOST],
            },
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        host = discovery_info.ip

        # Store discovered host for later use
        self._discovered_host = host

        # Check if we already have this device configured by MAC address or hostname
        # Set a temporary unique ID based on the MAC address
        await self.async_set_unique_id(discovery_info.macaddress)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Try to get device info without authentication to get device name
        # But continue with discovery even if this fails
        session = async_get_clientsession(self.hass)
        device_name = None

        for base_url in candidate_base_urls(host):
            client = Teltasync(
                base_url=base_url,
                username="",  # No credentials yet
                password="",
                session=session,
                verify_ssl=False,  # DHCP discovery typically on local network
            )

            try:
                # Try to get device info from unauthorized endpoint
                device_info = await client.get_device_info()
                device_name = getattr(device_info, "device_name", None)
                break
            except (TeltonikaConnectionError, TeltonikaAuthenticationError, Exception):  # noqa: BLE001
                # Device might require auth - that's okay, we'll continue anyway
                continue
            finally:
                await client.close()

        # Store discovery info for the user step
        self.context["title_placeholders"] = {
            "name": device_name or "Teltonika Device",
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
                    CONF_VALIDATE_SSL: False,
                }
                info = await validate_input(self.hass, data)

                # Update unique ID to use device serial instead of MAC address
                if info["serial"]:
                    await self.async_set_unique_id(
                        info["serial"], raise_on_progress=False
                    )
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: info["host"],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_VALIDATE_SSL: False,
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
