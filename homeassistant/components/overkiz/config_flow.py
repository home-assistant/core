"""Config flow for Overkiz integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from aiohttp import ClientConnectorError, ClientError
from pyoverkiz.client import OverkizClient
from pyoverkiz.const import SERVERS_WITH_LOCAL_API, SUPPORTED_SERVERS
from pyoverkiz.enums import APIType, Server
from pyoverkiz.exceptions import (
    BadCredentialsException,
    CozyTouchBadCredentialsException,
    MaintenanceException,
    NotSuchTokenException,
    TooManyAttemptsBannedException,
    TooManyRequestsException,
    UnknownUserException,
)
from pyoverkiz.models import OverkizServer
from pyoverkiz.obfuscate import obfuscate_id
from pyoverkiz.utils import generate_local_server, is_overkiz_gateway
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp, zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    CONF_API_TYPE,
    CONF_SERVER,
    DEFAULT_SERVER,
    DOMAIN,
    LOGGER,
)


class DeveloperModeDisabled(HomeAssistantError):
    """Error to indicate Somfy Developer Mode is disabled."""


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Overkiz (by Somfy)."""

    VERSION = 2

    _config_entry: ConfigEntry | None
    _api_type: APIType
    _user: None | str
    _server: str
    _host: str

    def __init__(self) -> None:
        """Initialize Overkiz Config Flow."""
        super().__init__()

        self._config_entry = None
        self._api_type = APIType.CLOUD
        self._user = None
        self._server = DEFAULT_SERVER
        self._host = "gateway-xxxx-xxxx-xxxx.local:8443"

    async def async_validate_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Validate user credentials."""
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        user_input[CONF_API_TYPE] = self._api_type

        # Local API
        if self._api_type == APIType.LOCAL:
            # Create session on Somfy cloud server to generate an access token for local API
            session = async_create_clientsession(self.hass)
            server = SUPPORTED_SERVERS[self._server]
            client = self._create_cloud_client(
                username=username, password=password, server=server
            )

            await client.login(register_event_listener=False)
            gateways = await client.get_gateways()

            gateway_id = ""
            for gateway in gateways:
                # Overkiz can return multiple gateways, but we only can generate a token
                # for the main gateway.
                if is_overkiz_gateway(gateway.id):
                    gateway_id = gateway.id

            developer_mode = await client.get_setup_option(
                f"developerMode-{gateway_id}"
            )

            if developer_mode is None:
                raise DeveloperModeDisabled

            token = await client.generate_local_token(gateway_id)
            await client.activate_local_token(
                gateway_id=gateway_id, token=token, label="Home Assistant/local"
            )

            # Verify SSL blocked by https://github.com/Somfy-Developer/Somfy-TaHoma-Developer-Mode/issues/5
            # Somfy (self-signed) SSL cert uses the wrong common name
            session = async_create_clientsession(self.hass, verify_ssl=False)

            # Local API
            local_client = OverkizClient(
                username="",
                password="",
                token=token,
                session=session,
                server=generate_local_server(host=user_input[CONF_HOST]),
            )

            await local_client.login()

            user_input[CONF_TOKEN] = token
        else:
            server = SUPPORTED_SERVERS[user_input[CONF_SERVER]]
            client = self._create_cloud_client(
                username=username, password=password, server=server
            )

            await client.login(register_event_listener=False)

        # Set main gateway id as unique id
        if gateways := await client.get_gateways():
            for gateway in gateways:
                if is_overkiz_gateway(gateway.id):
                    gateway_id = gateway.id
                    await self.async_set_unique_id(gateway_id)

        return user_input

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step via config flow."""
        if user_input:
            self._server = user_input[CONF_SERVER]

            # Some Overkiz hubs do support a local API
            # Users can choose between local or cloud API.
            if self._server in SERVERS_WITH_LOCAL_API:
                return await self.async_step_local_or_cloud()

            return await self.async_step_cloud()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVER, default=self._server): vol.In(
                        {key: hub.name for key, hub in SUPPORTED_SERVERS.items()}
                    ),
                }
            ),
        )

    async def async_step_local_or_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Users can choose between local API or cloud API via config flow."""
        if user_input:
            self._api_type = user_input[CONF_API_TYPE]

            if self._api_type == APIType.LOCAL:
                return await self.async_step_local()

            return await self.async_step_cloud()

        return self.async_show_form(
            step_id="local_or_cloud",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TYPE): vol.In(
                        {
                            APIType.LOCAL: "Local API",
                            APIType.CLOUD: "Cloud API",
                        }
                    ),
                }
            ),
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the cloud authentication step via config flow."""
        errors: dict[str, str] = {}
        description_placeholders = {}

        if user_input:
            self._user = user_input[CONF_USERNAME]
            user_input[
                CONF_SERVER
            ] = self._server  # inherit the server from previous step

            try:
                await self.async_validate_input(user_input)
            except TooManyRequestsException:
                errors["base"] = "too_many_requests"
            except BadCredentialsException as exception:
                # If authentication with CozyTouch auth server is valid, but token is invalid
                # for Overkiz API server, the hardware is not supported.
                if user_input[
                    CONF_SERVER
                ] == Server.ATLANTIC_COZYTOUCH and not isinstance(
                    exception, CozyTouchBadCredentialsException
                ):
                    description_placeholders["unsupported_device"] = "CozyTouch"
                    errors["base"] = "unsupported_hardware"
                else:
                    errors["base"] = "invalid_auth"
            except (TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            except MaintenanceException:
                errors["base"] = "server_in_maintenance"
            except TooManyAttemptsBannedException:
                errors["base"] = "too_many_attempts"
            except UnknownUserException:
                # Somfy Protect accounts are not supported since they don't use
                # the Overkiz API server. Login will return unknown user.
                description_placeholders["unsupported_device"] = "Somfy Protect"
                errors["base"] = "unsupported_hardware"
            except Exception as exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                LOGGER.exception(exception)
            else:
                if self._config_entry:
                    if self._config_entry.unique_id != self.unique_id:
                        return self.async_abort(reason="reauth_wrong_account")

                    # Update existing entry during reauth
                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        data={
                            **self._config_entry.data,
                            **user_input,
                        },
                    )

                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(
                            self._config_entry.entry_id
                        )
                    )

                    return self.async_abort(reason="reauth_successful")

                # Create new entry
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=self._user): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the local authentication step via config flow."""
        errors = {}
        description_placeholders = {}

        if user_input:
            self._host = user_input[CONF_HOST]
            self._user = user_input[CONF_USERNAME]
            user_input[
                CONF_SERVER
            ] = self._server  # inherit the server from previous step

            try:
                user_input = await self.async_validate_input(user_input)
            except TooManyRequestsException:
                errors["base"] = "too_many_requests"
            except BadCredentialsException:
                errors["base"] = "invalid_auth"
            except (TimeoutError, ClientError, ClientConnectorError):
                errors["base"] = "cannot_connect"
            except MaintenanceException:
                errors["base"] = "server_in_maintenance"
            except TooManyAttemptsBannedException:
                errors["base"] = "too_many_attempts"
            except NotSuchTokenException:
                errors["base"] = "not_such_token"
            except DeveloperModeDisabled:
                errors["base"] = "developer_mode_disabled"
            except UnknownUserException:
                # Somfy Protect accounts are not supported since they don't use
                # the Overkiz API server. Login will return unknown user.
                description_placeholders["unsupported_device"] = "Somfy Protect"
                errors["base"] = "unsupported_hardware"
            except Exception as exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                LOGGER.exception(exception)
            else:
                if self._config_entry:
                    if self._config_entry.unique_id != self.unique_id:
                        return self.async_abort(reason="reauth_wrong_account")

                    # Update existing entry during reauth
                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        data={
                            **self._config_entry.data,
                            **user_input,
                        },
                    )

                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(
                            self._config_entry.entry_id
                        )
                    )

                    return self.async_abort(reason="reauth_successful")

                # Create new entry
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                    vol.Required(CONF_USERNAME, default=self._user): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle DHCP discovery."""
        hostname = discovery_info.hostname
        gateway_id = hostname[8:22]
        self._host = f"gateway-{gateway_id}.local:8443"

        LOGGER.debug("DHCP discovery detected gateway %s", obfuscate_id(gateway_id))
        return await self._process_discovery(gateway_id)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle ZeroConf discovery."""
        properties = discovery_info.properties
        gateway_id = properties["gateway_pin"]
        hostname = discovery_info.hostname

        LOGGER.debug(
            "ZeroConf discovery detected gateway %s on %s (%s)",
            obfuscate_id(gateway_id),
            hostname,
            discovery_info.type,
        )

        if discovery_info.type == "_kizbox._tcp.local.":
            self._host = f"gateway-{gateway_id}.local:8443"

        if discovery_info.type == "_kizboxdev._tcp.local.":
            self._host = f"{discovery_info.hostname[:-1]}:{discovery_info.port}"
            self._api_type = APIType.LOCAL

        return await self._process_discovery(gateway_id)

    async def _process_discovery(self, gateway_id: str) -> FlowResult:
        """Handle discovery of a gateway."""
        await self.async_set_unique_id(gateway_id)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"gateway_id": gateway_id}

        return await self.async_step_user()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauth."""
        self._config_entry = cast(
            ConfigEntry,
            self.hass.config_entries.async_get_entry(self.context["entry_id"]),
        )

        self.context["title_placeholders"] = {
            "gateway_id": self._config_entry.unique_id
        }

        self._user = self._config_entry.data[CONF_USERNAME]
        self._server = self._config_entry.data[CONF_SERVER]
        self._api_type = self._config_entry.data[CONF_API_TYPE]

        return await self.async_step_user(dict(entry_data))

    def _create_cloud_client(
        self, username: str, password: str, server: OverkizServer
    ) -> OverkizClient:
        session = async_create_clientsession(self.hass)
        client = OverkizClient(
            username=username, password=password, server=server, session=session
        )

        return client
