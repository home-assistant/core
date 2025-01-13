"""Config flow for AVM FRITZ!SmartHome."""

from __future__ import annotations

from collections.abc import Mapping
import ipaddress
from typing import Any, Self
from urllib.parse import urlparse

from pyfritzhome import Fritzhome, LoginError
from requests.exceptions import HTTPError
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import DEFAULT_HOST, DEFAULT_USERNAME, DOMAIN

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

DATA_SCHEMA_CONFIRM = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

RESULT_INVALID_AUTH = "invalid_auth"
RESULT_NO_DEVICES_FOUND = "no_devices_found"
RESULT_NOT_SUPPORTED = "not_supported"
RESULT_SUCCESS = "success"


class FritzboxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a AVM FRITZ!SmartHome config flow."""

    VERSION = 1

    _name: str

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None
        self._password: str | None = None
        self._username: str | None = None

    def _get_entry(self, name: str) -> ConfigFlowResult:
        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: self._host,
                CONF_PASSWORD: self._password,
                CONF_USERNAME: self._username,
            },
        )

    async def async_try_connect(self) -> str:
        """Try to connect and check auth."""
        return await self.hass.async_add_executor_job(self._try_connect)

    def _try_connect(self) -> str:
        """Try to connect and check auth."""
        fritzbox = Fritzhome(
            host=self._host, user=self._username, password=self._password
        )
        try:
            fritzbox.login()
            fritzbox.get_device_elements()
            fritzbox.logout()
        except LoginError:
            return RESULT_INVALID_AUTH
        except HTTPError:
            return RESULT_NOT_SUPPORTED
        except OSError:
            return RESULT_NO_DEVICES_FOUND
        return RESULT_SUCCESS

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            self._host = user_input[CONF_HOST]
            self._name = str(user_input[CONF_HOST])
            self._password = user_input[CONF_PASSWORD]
            self._username = user_input[CONF_USERNAME]

            result = await self.async_try_connect()

            if result == RESULT_SUCCESS:
                return self._get_entry(self._name)
            if result != RESULT_INVALID_AUTH:
                return self.async_abort(reason=result)
            errors["base"] = result

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA_USER, errors=errors
        )

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by discovery."""
        host = urlparse(discovery_info.ssdp_location).hostname
        assert isinstance(host, str)

        if (
            ipaddress.ip_address(host).version == 6
            and ipaddress.ip_address(host).is_link_local
        ):
            return self.async_abort(reason="ignore_ip6_link_local")

        if uuid := discovery_info.upnp.get(ssdp.ATTR_UPNP_UDN):
            uuid = uuid.removeprefix("uuid:")
            await self.async_set_unique_id(uuid)
            self._abort_if_unique_id_configured({CONF_HOST: host})

        self._host = host
        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="already_in_progress")

        # update old and user-configured config entries
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_HOST] == host:
                if uuid and not entry.unique_id:
                    self.hass.config_entries.async_update_entry(entry, unique_id=uuid)
                return self.async_abort(reason="already_configured")

        self._name = str(discovery_info.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME) or host)

        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_confirm()

    def is_matching(self, other_flow: Self) -> bool:
        """Return True if other_flow is matching this flow."""
        return other_flow._host == self._host  # noqa: SLF001

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of discovered node."""
        errors = {}

        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            self._username = user_input[CONF_USERNAME]
            result = await self.async_try_connect()

            if result == RESULT_SUCCESS:
                return self._get_entry(self._name)
            if result != RESULT_INVALID_AUTH:
                return self.async_abort(reason=result)
            errors["base"] = result

        return self.async_show_form(
            step_id="confirm",
            data_schema=DATA_SCHEMA_CONFIRM,
            description_placeholders={"name": self._name},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Trigger a reauthentication flow."""
        self._host = entry_data[CONF_HOST]
        self._name = str(entry_data[CONF_HOST])
        self._username = entry_data[CONF_USERNAME]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow."""
        errors = {}

        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            self._username = user_input[CONF_USERNAME]

            result = await self.async_try_connect()

            if result == RESULT_SUCCESS:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data={
                        CONF_HOST: self._host,
                        CONF_PASSWORD: self._password,
                        CONF_USERNAME: self._username,
                    },
                )
            if result != RESULT_INVALID_AUTH:
                return self.async_abort(reason=result)
            errors["base"] = result

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=self._username): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"name": self._name},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]

            reconfigure_entry = self._get_reconfigure_entry()
            self._username = reconfigure_entry.data[CONF_USERNAME]
            self._password = reconfigure_entry.data[CONF_PASSWORD]

            result = await self.async_try_connect()

            if result == RESULT_SUCCESS:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: self._host},
                )
            errors["base"] = result

        host = self._get_reconfigure_entry().data[CONF_HOST]
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host): str,
                }
            ),
            description_placeholders={"name": host},
            errors=errors,
        )
