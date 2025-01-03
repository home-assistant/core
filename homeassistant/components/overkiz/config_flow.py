"""Config flow for Overkiz integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from aiohttp import ClientConnectorCertificateError, ClientError
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

from homeassistant.components import dhcp, zeroconf
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_API_TYPE, CONF_HUB, DEFAULT_SERVER, DOMAIN, LOGGER


class DeveloperModeDisabled(HomeAssistantError):
    """Error to indicate Somfy Developer Mode is disabled."""


class OverkizConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Overkiz (by Somfy)."""

    VERSION = 1

    _api_type: APIType = APIType.CLOUD
    _user: str | None = None
    _server: str = DEFAULT_SERVER
    _host: str = "gateway-xxxx-xxxx-xxxx.local:8443"

    async def async_validate_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Validate user credentials."""
        user_input[CONF_API_TYPE] = self._api_type

        client = self._create_cloud_client(
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            server=SUPPORTED_SERVERS[user_input[CONF_HUB]],
        )
        await client.login(register_event_listener=False)

        #  For Local API, we create and activate a local token
        if self._api_type == APIType.LOCAL:
            user_input[CONF_TOKEN] = await self._create_local_api_token(
                cloud_client=client,
                host=user_input[CONF_HOST],
                verify_ssl=user_input[CONF_VERIFY_SSL],
            )

        # Set main gateway id as unique id
        if gateways := await client.get_gateways():
            for gateway in gateways:
                if is_overkiz_gateway(gateway.id):
                    gateway_id = gateway.id
                    await self.async_set_unique_id(gateway_id, raise_on_progress=False)

        return user_input

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step via config flow."""
        if user_input:
            self._server = user_input[CONF_HUB]

            # Some Overkiz hubs do support a local API
            # Users can choose between local or cloud API.
            if self._server in SERVERS_WITH_LOCAL_API:
                return await self.async_step_local_or_cloud()

            return await self.async_step_cloud()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HUB, default=self._server): vol.In(
                        {key: hub.name for key, hub in SUPPORTED_SERVERS.items()}
                    ),
                }
            ),
        )

    async def async_step_local_or_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Handle the cloud authentication step via config flow."""
        errors: dict[str, str] = {}
        description_placeholders = {}

        if user_input:
            self._user = user_input[CONF_USERNAME]

            # inherit the server from previous step
            user_input[CONF_HUB] = self._server

            try:
                await self.async_validate_input(user_input)
            except TooManyRequestsException:
                errors["base"] = "too_many_requests"
            except BadCredentialsException as exception:
                # If authentication with CozyTouch auth server is valid, but token is invalid
                # for Overkiz API server, the hardware is not supported.
                if user_input[CONF_HUB] in {
                    Server.ATLANTIC_COZYTOUCH,
                    Server.SAUTER_COZYTOUCH,
                    Server.THERMOR_COZYTOUCH,
                } and not isinstance(exception, CozyTouchBadCredentialsException):
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
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
                LOGGER.exception("Unknown error")
            else:
                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch(reason="reauth_wrong_account")

                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=user_input
                    )

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
    ) -> ConfigFlowResult:
        """Handle the local authentication step via config flow."""
        errors = {}
        description_placeholders = {}

        if user_input:
            self._host = user_input[CONF_HOST]
            self._user = user_input[CONF_USERNAME]

            # inherit the server from previous step
            user_input[CONF_HUB] = self._server

            try:
                user_input = await self.async_validate_input(user_input)
            except TooManyRequestsException:
                errors["base"] = "too_many_requests"
            except BadCredentialsException:
                errors["base"] = "invalid_auth"
            except ClientConnectorCertificateError as exception:
                errors["base"] = "certificate_verify_failed"
                LOGGER.debug(exception)
            except (TimeoutError, ClientError) as exception:
                errors["base"] = "cannot_connect"
                LOGGER.debug(exception)
            except MaintenanceException:
                errors["base"] = "server_in_maintenance"
            except TooManyAttemptsBannedException:
                errors["base"] = "too_many_attempts"
            except NotSuchTokenException:
                errors["base"] = "no_such_token"
            except DeveloperModeDisabled:
                errors["base"] = "developer_mode_disabled"
            except UnknownUserException:
                # Somfy Protect accounts are not supported since they don't use
                # the Overkiz API server. Login will return unknown user.
                description_placeholders["unsupported_device"] = "Somfy Protect"
                errors["base"] = "unsupported_hardware"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
                LOGGER.exception("Unknown error")
            else:
                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch(reason="reauth_wrong_account")

                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=user_input
                    )

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
                    vol.Required(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        hostname = discovery_info.hostname
        gateway_id = hostname[8:22]
        self._host = f"gateway-{gateway_id}.local:8443"

        LOGGER.debug("DHCP discovery detected gateway %s", obfuscate_id(gateway_id))
        return await self._process_discovery(gateway_id)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
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

    async def _process_discovery(self, gateway_id: str) -> ConfigFlowResult:
        """Handle discovery of a gateway."""
        await self.async_set_unique_id(gateway_id)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"gateway_id": gateway_id}

        return await self.async_step_user()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth."""
        # overkiz entries always have unique IDs
        self.context["title_placeholders"] = {"gateway_id": cast(str, self.unique_id)}

        self._user = entry_data[CONF_USERNAME]
        self._server = entry_data[CONF_HUB]
        self._api_type = entry_data.get(CONF_API_TYPE, APIType.CLOUD)

        if self._api_type == APIType.LOCAL:
            self._host = entry_data[CONF_HOST]

        return await self.async_step_user(dict(entry_data))

    def _create_cloud_client(
        self, username: str, password: str, server: OverkizServer
    ) -> OverkizClient:
        session = async_create_clientsession(self.hass)
        return OverkizClient(
            username=username, password=password, server=server, session=session
        )

    async def _create_local_api_token(
        self, cloud_client: OverkizClient, host: str, verify_ssl: bool
    ) -> str:
        """Create local API token."""
        # Create session on Somfy cloud server to generate an access token for local API
        gateways = await cloud_client.get_gateways()

        gateway_id = ""
        for gateway in gateways:
            # Overkiz can return multiple gateways, but we only can generate a token
            # for the main gateway.
            if is_overkiz_gateway(gateway.id):
                gateway_id = gateway.id

        developer_mode = await cloud_client.get_setup_option(
            f"developerMode-{gateway_id}"
        )

        if developer_mode is None:
            raise DeveloperModeDisabled

        token = await cloud_client.generate_local_token(gateway_id)
        await cloud_client.activate_local_token(
            gateway_id=gateway_id, token=token, label="Home Assistant/local"
        )

        session = async_create_clientsession(self.hass, verify_ssl=verify_ssl)

        # Local API
        local_client = OverkizClient(
            username="",
            password="",
            token=token,
            session=session,
            server=generate_local_server(host=host),
            verify_ssl=verify_ssl,
        )

        await local_client.login()

        return token
