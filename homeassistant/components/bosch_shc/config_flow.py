"""Config flow for Bosch Smart Home Controller integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from os import makedirs
from typing import Any, cast

from boschshcpy import SHCRegisterClient, SHCSession
from boschshcpy.exceptions import (
    SHCAuthenticationError,
    SHCConnectionError,
    SHCRegistrationError,
    SHCSessionError,
)
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOSTNAME,
    CONF_SHC_CERT,
    CONF_SHC_KEY,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

HOST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


def write_tls_asset(hass: HomeAssistant, filename: str, asset: bytes) -> None:
    """Write the tls assets to disk."""
    makedirs(hass.config.path(DOMAIN), exist_ok=True)
    with open(hass.config.path(DOMAIN, filename), "w", encoding="utf8") as file_handle:
        file_handle.write(asset.decode("utf-8"))


def create_credentials_and_validate(
    hass: HomeAssistant,
    host: str,
    user_input: dict[str, Any],
    zeroconf_instance: zeroconf.HaZeroconf,
) -> dict[str, Any] | None:
    """Create and store credentials and validate session."""
    helper = SHCRegisterClient(host, user_input[CONF_PASSWORD])
    result = helper.register(host, "HomeAssistant")

    if result is not None:
        write_tls_asset(hass, CONF_SHC_CERT, result["cert"])
        write_tls_asset(hass, CONF_SHC_KEY, result["key"])

        session = SHCSession(
            host,
            hass.config.path(DOMAIN, CONF_SHC_CERT),
            hass.config.path(DOMAIN, CONF_SHC_KEY),
            True,
            zeroconf_instance,
        )
        session.authenticate()

    return result


def get_info_from_host(
    hass: HomeAssistant, host: str, zeroconf_instance: zeroconf.HaZeroconf
) -> dict[str, str | None]:
    """Get information from host."""
    session = SHCSession(
        host,
        "",
        "",
        True,
        zeroconf_instance,
    )
    information = session.mdns_info()
    return {"title": information.name, "unique_id": information.unique_id}


class BoschSHCConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch SHC."""

    VERSION = 1
    info: dict[str, str | None]
    host: str

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
                data_schema=HOST_SCHEMA,
            )
        self.host = user_input[CONF_HOST]
        self.info = await self._get_info(self.host)
        return await self.async_step_credentials()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.host = user_input[CONF_HOST]
            try:
                self.info = await self._get_info(self.host)
            except SHCConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(self.info["unique_id"])
                self._abort_if_unique_id_configured({CONF_HOST: self.host})
                return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user", data_schema=HOST_SCHEMA, errors=errors
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            zeroconf_instance = await zeroconf.async_get_instance(self.hass)
            try:
                result = await self.hass.async_add_executor_job(
                    create_credentials_and_validate,
                    self.hass,
                    self.host,
                    user_input,
                    zeroconf_instance,
                )
            except SHCAuthenticationError:
                errors["base"] = "invalid_auth"
            except SHCConnectionError:
                errors["base"] = "cannot_connect"
            except SHCSessionError as err:
                _LOGGER.warning("Session error: %s", err.message)
                errors["base"] = "session_error"
            except SHCRegistrationError as err:
                _LOGGER.warning("Registration error: %s", err.message)
                errors["base"] = "pairing_failed"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                assert result
                entry_data = {
                    CONF_SSL_CERTIFICATE: self.hass.config.path(DOMAIN, CONF_SHC_CERT),
                    CONF_SSL_KEY: self.hass.config.path(DOMAIN, CONF_SHC_KEY),
                    CONF_HOST: self.host,
                    CONF_TOKEN: result["token"],
                    CONF_HOSTNAME: result["token"].split(":", 1)[1],
                }
                existing_entry = await self.async_set_unique_id(self.info["unique_id"])
                if existing_entry:
                    return self.async_update_reload_and_abort(
                        existing_entry,
                        data=entry_data,
                    )

                return self.async_create_entry(
                    title=cast(str, self.info["title"]),
                    data=entry_data,
                )
        else:
            user_input = {}

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                ): str,
            }
        )

        return self.async_show_form(
            step_id="credentials", data_schema=schema, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        if not discovery_info.name.startswith("Bosch SHC"):
            return self.async_abort(reason="not_bosch_shc")

        try:
            self.info = await self._get_info(discovery_info.host)
        except SHCConnectionError:
            return self.async_abort(reason="cannot_connect")
        self.host = discovery_info.host

        local_name = discovery_info.hostname[:-1]
        node_name = local_name.removesuffix(".local")

        await self.async_set_unique_id(self.info["unique_id"])
        self._abort_if_unique_id_configured({CONF_HOST: self.host})
        self.context["title_placeholders"] = {"name": node_name}
        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirm."""
        errors: dict[str, str] = {}
        if user_input is not None:
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "model": "Bosch SHC",
                "host": self.host,
            },
            errors=errors,
        )

    async def _get_info(self, host: str) -> dict[str, str | None]:
        """Get additional information."""
        zeroconf_instance = await zeroconf.async_get_instance(self.hass)

        return await self.hass.async_add_executor_job(
            get_info_from_host,
            self.hass,
            host,
            zeroconf_instance,
        )
