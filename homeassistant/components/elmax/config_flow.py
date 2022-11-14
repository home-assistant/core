"""Config flow for elmax-cloud integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from elmax_api.exceptions import ElmaxBadLoginError, ElmaxBadPinError, ElmaxNetworkError
from elmax_api.http import Elmax, ElmaxLocal
from elmax_api.model.panel import PanelEntry
import httpx
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .common import get_direct_api_url
from .const import (
    CONF_ELMAX_MODE,
    CONF_ELMAX_MODE_CLOUD,
    CONF_ELMAX_MODE_DIRECT,
    CONF_ELMAX_MODE_DIRECT_HOST,
    CONF_ELMAX_MODE_DIRECT_PORT,
    CONF_ELMAX_MODE_DIRECT_SSL,
    CONF_ELMAX_MODE_DIRECT_FOLLOW_MDNS,
    CONF_ELMAX_PANEL_ID,
    CONF_ELMAX_PANEL_NAME,
    CONF_ELMAX_PANEL_PIN,
    CONF_ELMAX_PASSWORD,
    CONF_ELMAX_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

LOGIN_FORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ELMAX_USERNAME): str,
        vol.Required(CONF_ELMAX_PASSWORD): str,
    }
)

CHOOSE_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ELMAX_MODE, default=CONF_ELMAX_MODE_CLOUD): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(
                        value=CONF_ELMAX_MODE_CLOUD,
                        label="Connect to Elmax Panel via Elmax Cloud APIs",
                    ),
                    SelectOptionDict(
                        value=CONF_ELMAX_MODE_DIRECT,
                        label="Connect to Elmax Panel via local/direct IP",
                    ),
                ],
                mode=SelectSelectorMode.LIST,
            )
        )
    }
)

DIRECT_SETUP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ELMAX_MODE_DIRECT_HOST): str,
        vol.Required(CONF_ELMAX_MODE_DIRECT_PORT): int,
        vol.Required(CONF_ELMAX_MODE_DIRECT_SSL): bool,
        vol.Required(CONF_ELMAX_MODE_DIRECT_FOLLOW_MDNS): bool,
        vol.Required(CONF_ELMAX_PANEL_PIN): str,
    }
)

ZEROCONF_SETUP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ELMAX_PANEL_PIN): str,
    }
)


def _store_panel_by_name(
        panel: PanelEntry, username: str, panel_names: dict[str, str]
) -> None:
    original_panel_name = panel.get_name_by_user(username=username)
    panel_id = panel.hash
    collisions_count = 0
    panel_name = original_panel_name
    while panel_name in panel_names:
        # Handle same-name collision.
        collisions_count += 1
        panel_name = f"{original_panel_name} ({collisions_count})"
    panel_names[panel_name] = panel_id


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for elmax-cloud."""

    VERSION = 1
    _client: Elmax
    _selected_mode: str
    _panel_pin: str
    _panel_id: str

    # Direct API variables
    _panel_direct_use_ssl: bool
    _panel_direct_hostname: str
    _panel_direct_port: int
    _panel_direct_follow_mdns: bool

    # Cloud API variables
    _cloud_username: str
    _cloud_password: str
    _reauth_cloud_username: str | None
    _reauth_cloud_panelid: str | None

    # Panel selection variables
    _panels_schema: vol.Schema
    _panel_names: dict

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the flow initiated by the user."""
        return await self.async_step_choose_mode(user_input=user_input)

    async def async_step_choose_mode(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle local vs cloud mode selection step."""
        errors: dict[str, Any] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="choose_mode", data_schema=CHOOSE_MODE_SCHEMA, errors=errors
            )

        self._selected_mode = user_input[CONF_ELMAX_MODE]
        if self._selected_mode == CONF_ELMAX_MODE_CLOUD:
            return self.async_show_form(
                step_id="cloud_setup", data_schema=None, errors=errors
            )
        # Assume mode direct.
        return self.async_show_form(
            step_id="direct_setup", data_schema=DIRECT_SETUP_SCHEMA, errors=errors
        )

    async def _test_direct_and_create_entry(self):
        """Test the direct connection to the Elmax panel and create and entry if successful."""
        # Attempt the connection to make sure the pin works. Also, take the chance to retrieve the panel ID via APIs.
        client_api_url = get_direct_api_url(host=self._panel_direct_hostname, port=self._panel_direct_port,
                                            ssl=self._panel_direct_use_ssl)
        client = ElmaxLocal(panel_api_url=client_api_url, panel_code=self._panel_pin)
        await client.login()
        # Retrieve the current panel status. If this succeeds, it means the
        # setup did complete successfully.
        status = await client.get_current_panel_status()
        return await self._check_unique_and_create_entry(
            unique_id=status.panel_id,
            title=f"Elmax Direct ({status.panel_id})",
            data={
                CONF_ELMAX_MODE: self._selected_mode,
                CONF_ELMAX_MODE_DIRECT_HOST: self._panel_direct_hostname,
                CONF_ELMAX_MODE_DIRECT_PORT: self._panel_direct_port,
                CONF_ELMAX_MODE_DIRECT_SSL: self._panel_direct_use_ssl,
                CONF_ELMAX_MODE_DIRECT_FOLLOW_MDNS: self._panel_direct_follow_mdns,
                CONF_ELMAX_PANEL_PIN: self._panel_pin,
                CONF_ELMAX_PANEL_ID: status.panel_id
            },
        )

    async def async_step_direct_setup(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle the direct setup step."""
        if user_input is None:
            return self.async_show_form(
                step_id="direct_setup",
                data_schema=DIRECT_SETUP_SCHEMA,
                errors=None,
            )

        self._panel_direct_hostname = user_input[CONF_ELMAX_MODE_DIRECT_HOST]
        self._panel_direct_port = user_input[CONF_ELMAX_MODE_DIRECT_PORT]
        self._panel_direct_use_ssl = user_input[CONF_ELMAX_MODE_DIRECT_SSL]
        self._panel_pin = user_input[CONF_ELMAX_PANEL_PIN]

        try:
            return await self._test_direct_and_create_entry()
        except (ElmaxNetworkError, httpx.ConnectError, httpx.ConnectTimeout):
            return self.async_show_form(
                step_id="direct_setup",
                data_schema=DIRECT_SETUP_SCHEMA,
                errors={"base": "network_error"},
            )
        except ElmaxBadLoginError:
            return self.async_show_form(
                step_id="direct_setup",
                data_schema=DIRECT_SETUP_SCHEMA,
                errors={"base": "invalid_auth"},
            )

    async def async_step_zeroconf_setup(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle the direct setup step triggered via zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_setup",
                data_schema=ZEROCONF_SETUP_SCHEMA,
                errors=None,
            )
        self._panel_pin = user_input[CONF_ELMAX_PANEL_PIN]
        try:
            return await self._test_direct_and_create_entry()
        except (ElmaxNetworkError, httpx.ConnectError, httpx.ConnectTimeout):
            return self.async_show_form(
                step_id="zeroconf_setup",
                data_schema=ZEROCONF_SETUP_SCHEMA,
                errors={"base": "network_error"},
            )
        except ElmaxBadLoginError:
            return self.async_show_form(
                step_id="zeroconf_setup",
                data_schema=ZEROCONF_SETUP_SCHEMA,
                errors={"base": "invalid_auth"},
            )

    async def _check_unique_and_create_entry(
            self, unique_id: str, title: str, data: Mapping[str, Any]
    ) -> FlowResult:
        # Make sure this is the only Elmax integration for this specific panel id.
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=title,
            data=data,
        )

    async def async_step_cloud_setup(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle the cloud setup flow."""
        # When invokes without parameters, show the login form.
        username = user_input[CONF_ELMAX_USERNAME]
        password = user_input[CONF_ELMAX_PASSWORD]

        # Otherwise, it means we are handling now the "submission" of the user form.
        # In this case, let's try to log in to the Elmax cloud and retrieve the available panels.
        try:
            client = await self._async_login(username=username, password=password)

        except ElmaxBadLoginError:
            return self.async_show_form(
                step_id="cloud_setup",
                data_schema=LOGIN_FORM_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        except ElmaxNetworkError:
            _LOGGER.exception("A network error occurred")
            return self.async_show_form(
                step_id="cloud_setup",
                data_schema=LOGIN_FORM_SCHEMA,
                errors={"base": "network_error"},
            )

        # If the login succeeded, retrieve the list of available panels and filter the online ones
        online_panels = [x for x in await client.list_control_panels() if x.online]

        # If no online panel was found, we display an error in the next UI.
        if not online_panels:
            return self.async_show_form(
                step_id="cloud_setup",
                data_schema=LOGIN_FORM_SCHEMA,
                errors={"base": "no_panel_online"},
            )

        # Show the panel selection.
        # We want the user to choose the panel using the associated name, we set up a mapping
        # dictionary to handle that case.
        panel_names: dict[str, str] = {}
        username = client.get_authenticated_username()
        for panel in online_panels:
            _store_panel_by_name(
                panel=panel, username=username, panel_names=panel_names
            )

        self._client = client
        self._panel_names = panel_names
        schema = vol.Schema(
            {
                vol.Required(CONF_ELMAX_PANEL_NAME): vol.In(self._panel_names.keys()),
                vol.Required(CONF_ELMAX_PANEL_PIN, default="000000"): str,
            }
        )
        self._panels_schema = schema
        self._cloud_username = username
        self._cloud_password = password
        # If everything went OK, proceed to panel selection.
        return await self.async_step_panels(user_input=None)

    async def async_step_panels(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Panel selection step."""
        errors: dict[str, Any] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="panels", data_schema=self._panels_schema, errors=errors
            )

        panel_name = user_input[CONF_ELMAX_PANEL_NAME]
        panel_pin = user_input[CONF_ELMAX_PANEL_PIN]

        # Lookup the panel id from the panel name.
        panel_id = self._panel_names[panel_name]

        # Try to list all the devices using the given PIN.
        try:
            await self._client.get_panel_status(
                control_panel_id=panel_id, pin=panel_pin
            )
        except ElmaxBadPinError:
            errors["base"] = "invalid_pin"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error occurred")
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="panels", data_schema=self._panels_schema, errors=errors
            )

        return await self._check_unique_and_create_entry(
            unique_id=panel_id,
            title=f"Elmax cloud {panel_name}",
            data={
                CONF_ELMAX_MODE: CONF_ELMAX_MODE_CLOUD,
                CONF_ELMAX_PANEL_ID: panel_id,
                CONF_ELMAX_PANEL_PIN: panel_pin,
                CONF_ELMAX_USERNAME: self._cloud_username,
                CONF_ELMAX_PASSWORD: self._cloud_password,
            },
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_cloud_username = entry_data.get(CONF_ELMAX_USERNAME)
        self._reauth_cloud_panelid = entry_data.get(CONF_ELMAX_PANEL_ID)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauthorization flow."""
        errors = {}
        if user_input is not None:
            panel_pin = user_input.get(CONF_ELMAX_PANEL_PIN)
            password = user_input.get(CONF_ELMAX_PASSWORD)
            entry = await self.async_set_unique_id(self._reauth_cloud_panelid)

            # Handle authentication, make sure the panel we are re-authenticating against is listed among results
            # and verify its pin is correct.
            try:
                # Test login.
                client = await self._async_login(
                    username=self._reauth_cloud_username, password=password
                )

                # Make sure the panel we are authenticating to is still available.
                panels = [
                    p
                    for p in await client.list_control_panels()
                    if p.hash == self._reauth_cloud_panelid
                ]
                if len(panels) < 1:
                    raise NoOnlinePanelsError()

                # Verify the pin is still valid.from
                await client.get_panel_status(
                    control_panel_id=self._reauth_cloud_panelid, pin=panel_pin
                )

                # If it is, proceed with configuration update.
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_ELMAX_PANEL_ID: self._reauth_cloud_panelid,
                        CONF_ELMAX_PANEL_PIN: panel_pin,
                        CONF_ELMAX_USERNAME: self._reauth_cloud_username,
                        CONF_ELMAX_PASSWORD: password,
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                self._reauth_cloud_username = None
                self._reauth_cloud_panelid = None
                return self.async_abort(reason="reauth_successful")

            except ElmaxBadLoginError:
                _LOGGER.error(
                    "Wrong credentials or failed login while re-authenticating"
                )
                errors["base"] = "invalid_auth"
            except NoOnlinePanelsError:
                _LOGGER.warning(
                    "Panel ID %s is no longer associated to this user",
                    self._reauth_cloud_panelid,
                )
                errors["base"] = "reauth_panel_disappeared"
            except ElmaxBadPinError:
                errors["base"] = "invalid_pin"

        # We want the user to re-authenticate only for the given panel id using the same login.
        # We pin them to the UI, so the user realizes she must log in with the appropriate credentials
        # for the that specific panel.
        schema = vol.Schema(
            {
                vol.Required(CONF_ELMAX_USERNAME): self._reauth_cloud_username,
                vol.Required(CONF_ELMAX_PASSWORD): str,
                vol.Required(CONF_ELMAX_PANEL_ID): self._reauth_cloud_panelid,
                vol.Required(CONF_ELMAX_PANEL_PIN): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )

    async def _async_handle_entry_match(self, local_id: str, remote_id: str, host: str, port: int,
                                        use_ssl: bool) -> None:
        # Look for another entry with the same PANEL_ID (local or remote).
        # If there already is a matching panel, take the change to notify the Coordinator
        # so that it uses the newly discovered IP address. This mitigates the issues
        # arising with DHCP and IP changes of the panels.
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_ELMAX_PANEL_ID] in (local_id, remote_id):
                # If the discovery finds another entry with the same ID, skip the notification.
                # However, if the discovery finds a new host for a panel that was already registered
                # for a given host (leave PORT comparison aside as we don't want to get notified twice
                # for HTTP and HTTPS), update the entry so that the integration "follows" the DHCP IP.
                if entry.data.get(CONF_ELMAX_MODE, CONF_ELMAX_MODE_CLOUD) == CONF_ELMAX_MODE_DIRECT \
                        and entry.data[CONF_ELMAX_MODE_DIRECT_HOST] != host \
                        and entry.data[CONF_ELMAX_MODE_DIRECT_SSL] == use_ssl \
                        and entry.data.get(CONF_ELMAX_MODE_DIRECT_FOLLOW_MDNS, False):
                    new_data = dict()
                    new_data.update(entry.data)
                    new_data[CONF_ELMAX_MODE_DIRECT_HOST] = host
                    new_data[CONF_ELMAX_MODE_DIRECT_PORT] = port
                    self.hass.config_entries.async_update_entry(entry,
                                                                unique_id=entry.unique_id,
                                                                data=new_data)
                # Abort the configuration, as there already is an entry for this PANEL-ID.
                self.async_abort(reason="already_configured")

    async def async_step_zeroconf(
            self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle device found via zeroconf."""
        host = discovery_info.host
        port = int(discovery_info.port)
        local_id = discovery_info.properties.get("idl")
        remote_id = discovery_info.properties.get("idr")
        use_ssl = discovery_info.type == "_elmax-ssl._tcp.local."
        await self._async_handle_entry_match(local_id, remote_id, host, port, use_ssl)

        self._selected_mode = CONF_ELMAX_MODE_DIRECT
        self._panel_direct_hostname = host
        self._panel_direct_port = port
        self._panel_direct_use_ssl = use_ssl
        self._panel_direct_follow_mdns = True

        return self.async_show_form(
            step_id="zeroconf_setup", data_schema=ZEROCONF_SETUP_SCHEMA
        )

    @staticmethod
    async def _async_login(username: str, password: str) -> Elmax:
        """Log in to the Elmax cloud and return the http client."""
        client = Elmax(username=username, password=password)
        await client.login()
        return client


class NoOnlinePanelsError(HomeAssistantError):
    """Error occurring when no online panel was found."""
