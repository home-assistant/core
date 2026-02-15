"""Config flow for AVM FRITZ!SmartHome."""

from __future__ import annotations

from collections.abc import Mapping
import ipaddress
from typing import TYPE_CHECKING, Any, Self

from pyfritzhome import Fritzhome, LoginError
from requests.exceptions import HTTPError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_PRESENTATION_URL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import DEFAULT_URL, DEFAULT_USERNAME, DEFAULT_VERIFY_SSL, DOMAIN

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)

DATA_SCHEMA_CONFIRM = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

RESULT_INVALID_AUTH = "invalid_auth"
RESULT_NO_DEVICES_FOUND = "no_devices_found"
RESULT_NOT_SUPPORTED = "not_supported"
RESULT_SUCCESS = "success"


class FritzboxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a AVM FRITZ!SmartHome config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    _name: str

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None
        self._port: int | None = None
        self._password: str | None = None
        self._username: str | None = None
        self._verify_ssl: bool = DEFAULT_VERIFY_SSL

    def _get_entry(self, name: str) -> ConfigFlowResult:
        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: self._host,
                CONF_PASSWORD: self._password,
                CONF_USERNAME: self._username,
                CONF_PORT: self._port,
                CONF_VERIFY_SSL: self._verify_ssl,
            },
        )

    async def async_try_connect(self) -> str:
        """Try to connect and check auth."""
        return await self.hass.async_add_executor_job(self._try_connect)

    def _try_connect(self) -> str:
        """Try to connect and check auth."""
        fritzbox = Fritzhome(
            host=self._host,
            user=self._username,
            password=self._password,
            port=self._port,
            ssl_verify=self._verify_ssl,
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
            url = URL(user_input[CONF_URL])
            self._host = f"{url.scheme}://{url.host}"
            self._port = url.port
            self._verify_ssl = user_input[CONF_VERIFY_SSL]
            self._password = user_input[CONF_PASSWORD]
            self._username = user_input[CONF_USERNAME]
            self._name = str(self._host)

            self._async_abort_entries_match({CONF_HOST: self._host})

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
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by discovery."""
        self._host = discovery_info.upnp[ATTR_UPNP_PRESENTATION_URL]
        represenation_url = URL(self._host)
        self._port = represenation_url.port or 80

        if TYPE_CHECKING:
            assert isinstance(represenation_url.host, str)

        if (
            ipaddress.ip_address(represenation_url.host).version == 6
            and ipaddress.ip_address(represenation_url.host).is_link_local
        ):
            return self.async_abort(reason="ignore_ip6_link_local")

        if uuid := discovery_info.upnp.get(ATTR_UPNP_UDN):
            uuid = uuid.removeprefix("uuid:")
            await self.async_set_unique_id(uuid)
            self._abort_if_unique_id_configured({CONF_HOST: self._host})

        if self.hass.config_entries.flow.async_has_matching_flow(self):
            return self.async_abort(reason="already_in_progress")

        # update old and user-configured config entries
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_HOST] == self._host:
                if uuid and not entry.unique_id:
                    self.hass.config_entries.async_update_entry(entry, unique_id=uuid)
                return self.async_abort(reason="already_configured")

        self._name = str(discovery_info.upnp.get(ATTR_UPNP_FRIENDLY_NAME) or self._host)

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
        self._port = entry_data[CONF_PORT]
        self._verify_ssl = entry_data[CONF_VERIFY_SSL]
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
                    data_updates={
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
        reconfigure_entry = self._get_reconfigure_entry()

        self._host = reconfigure_entry.data[CONF_HOST]
        self._port = reconfigure_entry.data[CONF_PORT]
        self._verify_ssl = reconfigure_entry.data[CONF_VERIFY_SSL]
        self._username = reconfigure_entry.data[CONF_USERNAME]
        self._password = reconfigure_entry.data[CONF_PASSWORD]

        if user_input is not None:
            url = URL(user_input[CONF_URL])
            self._host = f"{url.scheme}://{url.host}"
            self._port = url.port
            self._verify_ssl = user_input[CONF_VERIFY_SSL]

            result = await self.async_try_connect()

            if result == RESULT_SUCCESS:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_VERIFY_SSL: self._verify_ssl,
                    },
                )
            errors["base"] = result

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=self._host): str,
                    vol.Required(CONF_VERIFY_SSL, default=self._verify_ssl): bool,
                }
            ),
            description_placeholders={"name": self._host},
            errors=errors,
        )
