"""Config flow for homee integration."""

from collections.abc import Mapping
import logging
from typing import Any

from pyHomee import (
    Homee,
    HomeeAuthFailedException as HomeeAuthenticationFailedException,
    HomeeConnectionFailedException,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    DOMAIN,
    RESULT_CANNOT_CONNECT,
    RESULT_INVALID_AUTH,
    RESULT_UNKNOWN_ERROR,
)

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class HomeeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for homee."""

    VERSION = 1

    homee: Homee
    _host: str
    _name: str
    _reauth_host: str
    _reauth_username: str

    async def _connect_homee(self) -> dict[str, str]:
        errors: dict[str, str] = {}
        try:
            await self.homee.get_access_token()
        except HomeeConnectionFailedException:
            errors["base"] = RESULT_CANNOT_CONNECT
        except HomeeAuthenticationFailedException:
            errors["base"] = RESULT_INVALID_AUTH
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = RESULT_UNKNOWN_ERROR
        else:
            _LOGGER.info("Got access token for homee")
            self.hass.loop.create_task(self.homee.run())
            _LOGGER.debug("Homee task created")
            await self.homee.wait_until_connected()
            _LOGGER.info("Homee connected")
            self.homee.disconnect()
            _LOGGER.debug("Homee disconnecting")
            await self.homee.wait_until_disconnected()
            _LOGGER.info("Homee config successfully tested")

            await self.async_set_unique_id(
                self.homee.settings.uid, raise_on_progress=self.source != SOURCE_USER
            )

            self._abort_if_unique_id_configured()

            _LOGGER.info("Created new homee entry with ID %s", self.homee.settings.uid)

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.homee = Homee(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            errors = await self._connect_homee()

            if not errors:
                return self.async_create_entry(
                    title=f"{self.homee.settings.homee_name} ({self.homee.host})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=AUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        # Ensure that an IPv4 address is received
        self._host = discovery_info.host
        self._name = discovery_info.hostname[6:18]
        if discovery_info.ip_address.version == 6:
            return self.async_abort(reason="ipv6_address")

        await self.async_set_unique_id(self._name)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        # Cause an auth-error to see if homee is reachable.
        self.homee = Homee(
            self._host,
            "dummy_username",
            "dummy_password",
        )
        errors = await self._connect_homee()
        if errors["base"] != RESULT_INVALID_AUTH:
            return self.async_abort(reason=RESULT_CANNOT_CONNECT)

        self.context["title_placeholders"] = {"name": self._name, "host": self._host}

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the configuration of the device."""

        errors: dict[str, str] = {}
        if user_input is not None:
            self.homee = Homee(
                self._host,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            errors = await self._connect_homee()

            if not errors:
                return self.async_create_entry(
                    title=f"{self.homee.settings.homee_name} ({self.homee.host})",
                    data={
                        CONF_HOST: self._host,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={
                CONF_HOST: self._name,
            },
            last_step=True,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        self._reauth_host = entry_data[CONF_HOST]
        self._reauth_username = entry_data[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}

        if user_input:
            self.homee = Homee(
                self._reauth_host, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            try:
                await self.homee.get_access_token()
            except HomeeConnectionFailedException:
                errors["base"] = RESULT_CANNOT_CONNECT
            except HomeeAuthenticationFailedException:
                errors["base"] = RESULT_INVALID_AUTH
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = RESULT_UNKNOWN_ERROR
            else:
                self.hass.loop.create_task(self.homee.run())
                await self.homee.wait_until_connected()
                self.homee.disconnect()
                await self.homee.wait_until_disconnected()

                await self.async_set_unique_id(self.homee.settings.uid)
                self._abort_if_unique_id_mismatch(reason="wrong_hub")

                _LOGGER.debug(
                    "Reauthenticated homee entry with ID %s", self.homee.settings.uid
                )
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=self._reauth_username): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={
                "host": self._reauth_host,
            },
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure flow."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input:
            self.homee = Homee(
                user_input[CONF_HOST],
                reconfigure_entry.data[CONF_USERNAME],
                reconfigure_entry.data[CONF_PASSWORD],
            )

            try:
                await self.homee.get_access_token()
            except HomeeConnectionFailedException:
                errors["base"] = RESULT_CANNOT_CONNECT
            except HomeeAuthenticationFailedException:
                errors["base"] = RESULT_INVALID_AUTH
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = RESULT_UNKNOWN_ERROR
            else:
                self.hass.loop.create_task(self.homee.run())
                await self.homee.wait_until_connected()
                self.homee.disconnect()
                await self.homee.wait_until_disconnected()

                await self.async_set_unique_id(self.homee.settings.uid)
                self._abort_if_unique_id_mismatch(reason="wrong_hub")

                _LOGGER.debug("Updated homee entry with ID %s", self.homee.settings.uid)
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data_updates=user_input
                )

        return self.async_show_form(
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=reconfigure_entry.data[CONF_HOST]
                    ): str
                }
            ),
            description_placeholders={"name": str(reconfigure_entry.unique_id)},
            errors=errors,
        )
