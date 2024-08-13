"""Config flow for elmax-cloud integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from elmax_api.exceptions import ElmaxBadLoginError, ElmaxBadPinError, ElmaxNetworkError
from elmax_api.http import Elmax, ElmaxLocal, GenericElmax
from elmax_api.model.panel import PanelEntry, PanelStatus
import httpx
import voluptuous as vol

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError

from .common import (
    build_direct_ssl_context,
    check_local_version_supported,
    get_direct_api_url,
)
from .const import (
    CONF_ELMAX_MODE,
    CONF_ELMAX_MODE_CLOUD,
    CONF_ELMAX_MODE_DIRECT,
    CONF_ELMAX_MODE_DIRECT_HOST,
    CONF_ELMAX_MODE_DIRECT_PORT,
    CONF_ELMAX_MODE_DIRECT_SSL,
    CONF_ELMAX_MODE_DIRECT_SSL_CERT,
    CONF_ELMAX_PANEL_ID,
    CONF_ELMAX_PANEL_NAME,
    CONF_ELMAX_PANEL_PIN,
    CONF_ELMAX_PASSWORD,
    CONF_ELMAX_USERNAME,
    DOMAIN,
    ELMAX_MODE_DIRECT_DEFAULT_HTTP_PORT,
    ELMAX_MODE_DIRECT_DEFAULT_HTTPS_PORT,
)

_LOGGER = logging.getLogger(__name__)

LOGIN_FORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ELMAX_USERNAME): str,
        vol.Required(CONF_ELMAX_PASSWORD): str,
    }
)

REAUTH_FORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ELMAX_USERNAME): str,
        vol.Required(CONF_ELMAX_PASSWORD): str,
        vol.Required(CONF_ELMAX_PANEL_PIN): str,
    }
)

DIRECT_SETUP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ELMAX_MODE_DIRECT_HOST): str,
        vol.Required(CONF_ELMAX_MODE_DIRECT_PORT, default=443): int,
        vol.Required(CONF_ELMAX_MODE_DIRECT_SSL, default=True): bool,
        vol.Required(CONF_ELMAX_PANEL_PIN): str,
    }
)

ZEROCONF_SETUP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ELMAX_PANEL_PIN): str,
        vol.Required(CONF_ELMAX_MODE_DIRECT_SSL, default=True): bool,
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


class ElmaxConfigFlow(ConfigFlow, domain=DOMAIN):
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
    _panel_direct_ssl_cert: str | None
    _panel_direct_http_port: int
    _panel_direct_https_port: int

    # Cloud API variables
    _cloud_username: str
    _cloud_password: str
    _reauth_cloud_username: str | None
    _reauth_cloud_panelid: str | None

    # Panel selection variables
    _panels_schema: vol.Schema
    _panel_names: dict
    _entry: ConfigEntry | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the flow initiated by the user."""
        return await self.async_step_choose_mode(user_input=user_input)

    async def async_step_choose_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle local vs cloud mode selection step."""
        return self.async_show_menu(
            step_id="choose_mode",
            menu_options={
                CONF_ELMAX_MODE_CLOUD: "Connect to Elmax Panel via Elmax Cloud APIs",
                CONF_ELMAX_MODE_DIRECT: "Connect to Elmax Panel via local/direct IP",
            },
        )

    async def _handle_direct_and_create_entry(
        self, fallback_step_id: str, schema: vol.Schema
    ) -> ConfigFlowResult:
        return await self._test_direct_and_create_entry()

    async def _test_direct_and_create_entry(self):
        """Test the direct connection to the Elmax panel and create and entry if successful."""
        ssl_context = None
        self._panel_direct_ssl_cert = None
        if self._panel_direct_use_ssl:
            # Fetch the remote certificate.
            # Local API is exposed via a self-signed SSL that we must add to our trust store.
            self._panel_direct_ssl_cert = (
                await GenericElmax.retrieve_server_certificate(
                    hostname=self._panel_direct_hostname,
                    port=self._panel_direct_port,
                )
            )
            ssl_context = build_direct_ssl_context(cadata=self._panel_direct_ssl_cert)

        # Attempt the connection to make sure the pin works. Also, take the chance to retrieve the panel ID via APIs.
        client_api_url = get_direct_api_url(
            host=self._panel_direct_hostname,
            port=self._panel_direct_port,
            use_ssl=self._panel_direct_use_ssl,
        )
        client = ElmaxLocal(
            panel_api_url=client_api_url,
            panel_code=self._panel_pin,
            ssl_context=ssl_context,
        )
        try:
            await client.login()
        except (ElmaxNetworkError, httpx.ConnectError, httpx.ConnectTimeout):
            return self.async_show_form(
                step_id=CONF_ELMAX_MODE_DIRECT,
                data_schema=DIRECT_SETUP_SCHEMA,
                errors={"base": "network_error"},
            )
        except ElmaxBadLoginError:
            return self.async_show_form(
                step_id=CONF_ELMAX_MODE_DIRECT,
                data_schema=DIRECT_SETUP_SCHEMA,
                errors={"base": "invalid_auth"},
            )

        # Retrieve the current panel status. If this succeeds, it means the
        # setup did complete successfully.
        panel_status: PanelStatus = await client.get_current_panel_status()

        # Make sure this is the only Elmax integration for this specific panel id.
        await self.async_set_unique_id(panel_status.panel_id)
        self._abort_if_unique_id_configured()

        return await self._check_unique_and_create_entry(
            unique_id=panel_status.panel_id,
            title=f"Elmax Direct {panel_status.panel_id}",
            data={
                CONF_ELMAX_MODE: self._selected_mode,
                CONF_ELMAX_MODE_DIRECT_HOST: self._panel_direct_hostname,
                CONF_ELMAX_MODE_DIRECT_PORT: self._panel_direct_port,
                CONF_ELMAX_MODE_DIRECT_SSL: self._panel_direct_use_ssl,
                CONF_ELMAX_PANEL_PIN: self._panel_pin,
                CONF_ELMAX_PANEL_ID: panel_status.panel_id,
                CONF_ELMAX_MODE_DIRECT_SSL_CERT: self._panel_direct_ssl_cert,
            },
        )

    async def async_step_direct(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle the direct setup step."""
        self._selected_mode = CONF_ELMAX_MODE_CLOUD
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_ELMAX_MODE_DIRECT,
                data_schema=DIRECT_SETUP_SCHEMA,
                errors=None,
            )

        self._panel_direct_hostname = user_input[CONF_ELMAX_MODE_DIRECT_HOST]
        self._panel_direct_port = user_input[CONF_ELMAX_MODE_DIRECT_PORT]
        self._panel_direct_use_ssl = user_input[CONF_ELMAX_MODE_DIRECT_SSL]
        self._panel_pin = user_input[CONF_ELMAX_PANEL_PIN]
        self._panel_direct_follow_mdns = True

        tmp_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ELMAX_MODE_DIRECT_HOST, default=self._panel_direct_hostname
                ): str,
                vol.Required(
                    CONF_ELMAX_MODE_DIRECT_PORT, default=self._panel_direct_port
                ): int,
                vol.Required(
                    CONF_ELMAX_MODE_DIRECT_SSL, default=self._panel_direct_use_ssl
                ): bool,
                vol.Required(CONF_ELMAX_PANEL_PIN, default=self._panel_pin): str,
            }
        )
        return await self._handle_direct_and_create_entry(
            fallback_step_id=CONF_ELMAX_MODE_DIRECT, schema=tmp_schema
        )

    async def async_step_zeroconf_setup(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle the direct setup step triggered via zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_setup",
                data_schema=ZEROCONF_SETUP_SCHEMA,
                errors=None,
            )
        self._panel_direct_use_ssl = user_input[CONF_ELMAX_MODE_DIRECT_SSL]
        self._panel_direct_port = (
            self._panel_direct_https_port
            if self._panel_direct_use_ssl
            else self._panel_direct_http_port
        )
        self._panel_pin = user_input[CONF_ELMAX_PANEL_PIN]
        tmp_schema = vol.Schema(
            {
                vol.Required(CONF_ELMAX_PANEL_PIN, default=self._panel_pin): str,
                vol.Required(
                    CONF_ELMAX_MODE_DIRECT_SSL, default=self._panel_direct_use_ssl
                ): bool,
            }
        )
        return await self._handle_direct_and_create_entry(
            fallback_step_id="zeroconf_setup", schema=tmp_schema
        )

    async def _check_unique_and_create_entry(
        self, unique_id: str, title: str, data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        # Make sure this is the only Elmax integration for this specific panel id.
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=title,
            data=data,
        )

    async def async_step_cloud(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle the cloud setup flow."""
        self._selected_mode = CONF_ELMAX_MODE_CLOUD

        # When invokes without parameters, show the login form.
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_ELMAX_MODE_CLOUD, data_schema=LOGIN_FORM_SCHEMA, errors={}
            )

        # Otherwise, it means we are handling now the "submission" of the user form.
        # In this case, let's try to log in to the Elmax cloud and retrieve the available panels.
        username = user_input[CONF_ELMAX_USERNAME]
        password = user_input[CONF_ELMAX_PASSWORD]
        try:
            client = await self._async_login(username=username, password=password)

        except ElmaxBadLoginError:
            return self.async_show_form(
                step_id=CONF_ELMAX_MODE_CLOUD,
                data_schema=LOGIN_FORM_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        except ElmaxNetworkError:
            _LOGGER.exception("A network error occurred")
            return self.async_show_form(
                step_id=CONF_ELMAX_MODE_CLOUD,
                data_schema=LOGIN_FORM_SCHEMA,
                errors={"base": "network_error"},
            )

        # If the login succeeded, retrieve the list of available panels and filter the online ones
        online_panels = [x for x in await client.list_control_panels() if x.online]

        # If no online panel was found, we display an error in the next UI.
        if not online_panels:
            return self.async_show_form(
                step_id=CONF_ELMAX_MODE_CLOUD,
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
    ) -> ConfigFlowResult:
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

        # Make sure this is the only elmax integration for this specific panel id.
        await self.async_set_unique_id(panel_id)
        self._abort_if_unique_id_configured()

        # Try to list all the devices using the given PIN.
        try:
            await self._client.get_panel_status(
                control_panel_id=panel_id, pin=panel_pin
            )
        except ElmaxBadPinError:
            errors["base"] = "invalid_pin"
        except Exception:
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._reauth_cloud_username = entry_data.get(CONF_ELMAX_USERNAME)
        self._reauth_cloud_panelid = entry_data.get(CONF_ELMAX_PANEL_ID)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow."""
        errors = {}
        if user_input is not None:
            username = user_input[CONF_ELMAX_USERNAME]
            password = user_input[CONF_ELMAX_PASSWORD]
            panel_pin = user_input[CONF_ELMAX_PANEL_PIN]
            await self.async_set_unique_id(self._reauth_cloud_panelid)

            # Handle authentication, make sure the panel we are re-authenticating against is listed among results
            # and verify its pin is correct.
            assert self._entry is not None
            try:
                # Test login.
                client = await self._async_login(username=username, password=password)
                # Make sure the panel we are authenticating to is still available.
                panels = [
                    p
                    for p in await client.list_control_panels()
                    if p.hash == self._entry.data[CONF_ELMAX_PANEL_ID]
                ]
                if len(panels) < 1:
                    raise NoOnlinePanelsError  # noqa: TRY301

                # Verify the pin is still valid.
                await client.get_panel_status(
                    control_panel_id=self._entry.data[CONF_ELMAX_PANEL_ID],
                    pin=panel_pin,
                )

            except ElmaxBadLoginError:
                errors["base"] = "invalid_auth"
            except NoOnlinePanelsError:
                errors["base"] = "reauth_panel_disappeared"
            except ElmaxBadPinError:
                errors["base"] = "invalid_pin"

            # If all went right, update the config entry
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={
                        CONF_ELMAX_PANEL_ID: self._entry.data[CONF_ELMAX_PANEL_ID],
                        CONF_ELMAX_PANEL_PIN: panel_pin,
                        CONF_ELMAX_USERNAME: username,
                        CONF_ELMAX_PASSWORD: password,
                    },
                )
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        # Otherwise start over and show the relative error message
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_FORM_SCHEMA, errors=errors
        )

    async def _async_handle_entry_match(
        self,
        local_id: str,
        remote_id: str | None,
        host: str,
        https_port: int,
        http_port: int,
    ) -> ConfigFlowResult | None:
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
                if (
                    entry.data.get(CONF_ELMAX_MODE, CONF_ELMAX_MODE_CLOUD)
                    == CONF_ELMAX_MODE_DIRECT
                    and entry.data[CONF_ELMAX_MODE_DIRECT_HOST] != host
                ):
                    new_data: dict[str, Any] = {}
                    new_data.update(entry.data)
                    new_data[CONF_ELMAX_MODE_DIRECT_HOST] = host
                    new_data[CONF_ELMAX_MODE_DIRECT_PORT] = (
                        https_port
                        if entry.data[CONF_ELMAX_MODE_DIRECT_SSL]
                        else http_port
                    )
                    self.hass.config_entries.async_update_entry(
                        entry, unique_id=entry.unique_id, data=new_data
                    )
                # Abort the configuration, as there already is an entry for this PANEL-ID.
                return self.async_abort(reason="already_configured")
        return None

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle device found via zeroconf."""
        host = discovery_info.host
        https_port = (
            int(discovery_info.port)
            if discovery_info.port is not None
            else ELMAX_MODE_DIRECT_DEFAULT_HTTPS_PORT
        )
        plain_http_port = discovery_info.properties.get(
            "http_port", ELMAX_MODE_DIRECT_DEFAULT_HTTP_PORT
        )
        plain_http_port = int(plain_http_port)
        local_id = discovery_info.properties.get("idl")
        remote_id = discovery_info.properties.get("idr")
        v2api_version = discovery_info.properties.get("v2")

        # Only deal with panels exposing v2 version
        if not check_local_version_supported(v2api_version):
            return self.async_abort(reason="not_supported")

        # Handle the discovered panel info. This is useful especially if the panel
        # changes its IP address while remaining perfectly configured.
        if (
            local_id is not None
            and (
                abort_result := await self._async_handle_entry_match(
                    local_id, remote_id, host, https_port, plain_http_port
                )
            )
            is not None
        ):
            return abort_result

        self._selected_mode = CONF_ELMAX_MODE_DIRECT
        self._panel_direct_hostname = host
        self._panel_direct_https_port = https_port
        self._panel_direct_http_port = plain_http_port
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
