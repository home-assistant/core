"""Config flow for Overkiz integration."""

from collections.abc import Mapping
import logging
from typing import Any, cast, override

from aiohttp import ClientConnectorCertificateError, ClientError
from pyoverkiz.auth.credentials import (
    LocalTokenCredentials,
    RexelTokenCredentials,
    UsernamePasswordCredentials,
)
from pyoverkiz.client import GatewayCandidate, OverkizClient
from pyoverkiz.const import (
    REXEL_OAUTH_CLIENT_ID,
    SERVERS_WITH_LOCAL_API,
    SUPPORTED_SERVERS,
)
from pyoverkiz.enums import APIType, Server
from pyoverkiz.exceptions import (
    ApplicationNotAllowedError,
    BadCredentialsError,
    CozyTouchBadCredentialsError,
    MaintenanceError,
    NoSuchTokenError,
    NotAuthenticatedError,
    TooManyAttemptsBannedError,
    TooManyRequestsError,
    UnknownUserError,
)
from pyoverkiz.obfuscate import obfuscate_id
from pyoverkiz.utils import create_local_server_config, is_overkiz_gateway
import voluptuous as vol

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_API_TYPE,
    CONF_GATEWAY_ID,
    CONF_HUB,
    DEFAULT_SERVER,
    DOMAIN,
    LOGGER,
)

LOCAL_API_DOCS_URL = (
    "https://www.home-assistant.io/integrations/overkiz/#local-api-support"
)
TOKEN_DOCS_URL = (
    "https://www.home-assistant.io/integrations/overkiz/#login-to-overkiz-local-api"
)


class OverkizConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for Overkiz (by Somfy)."""

    DOMAIN = DOMAIN
    VERSION = 1
    MINOR_VERSION = 2

    _verify_ssl: bool = True
    _api_type: APIType = APIType.CLOUD
    _user: str | None = None
    _server: str = DEFAULT_SERVER
    _host: str = "gateway-xxxx-xxxx-xxxx.local:8443"

    _rexel_gateways: list[GatewayCandidate]
    _rexel_oauth_data: dict[str, Any]

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return LOGGER

    async def async_validate_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Validate user credentials."""
        user_input[CONF_API_TYPE] = self._api_type

        if self._api_type == APIType.LOCAL:
            user_input[CONF_VERIFY_SSL] = self._verify_ssl
            session = async_create_clientsession(
                self.hass, verify_ssl=user_input[CONF_VERIFY_SSL]
            )
            client = OverkizClient(
                server=create_local_server_config(host=user_input[CONF_HOST]),
                credentials=LocalTokenCredentials(user_input[CONF_TOKEN]),
                session=session,
                verify_ssl=user_input[CONF_VERIFY_SSL],
            )
        else:  # APIType.CLOUD
            session = async_create_clientsession(self.hass)
            client = OverkizClient(
                server=user_input[CONF_HUB],
                credentials=UsernamePasswordCredentials(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                ),
                session=session,
            )

        await client.login(register_event_listener=False)

        # Set main gateway id as unique id
        if gateways := await client.get_gateways():
            for gateway in gateways:
                if is_overkiz_gateway(gateway.id):
                    await self.async_set_unique_id(gateway.id, raise_on_progress=False)
                    break

        return user_input

    def _async_finish_validated_entry(
        self, user_input: dict[str, Any], title: str
    ) -> ConfigFlowResult:
        """Create or update the entry once credentials have been validated."""
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="reauth_wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=user_input
            )

        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="reconfigure_wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=user_input
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=user_input)

    @override
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

            # Rexel authenticates via OAuth2 (Azure AD B2C with PKCE).
            if self._server == Server.REXEL:
                return await self.async_step_pick_implementation()

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
            description_placeholders={"local_api_docs": LOCAL_API_DOCS_URL},
        )

    @override
    async def async_step_pick_implementation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start the Rexel OAuth2 flow, re-importing the credential if removed."""
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(REXEL_OAUTH_CLIENT_ID, "", name="Rexel"),
        )
        return await super().async_step_pick_implementation(user_input)

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the cloud authentication step via config flow."""
        errors: dict[str, str] = {}
        description_placeholders = {}

        if user_input:
            self._user = user_input[CONF_USERNAME]
            user_input[CONF_HUB] = self._server

            try:
                await self.async_validate_input(user_input)
            except TooManyRequestsError:
                errors["base"] = "too_many_requests"
            except ApplicationNotAllowedError:
                errors["base"] = "application_not_allowed"
            except (BadCredentialsError, NotAuthenticatedError) as exception:
                # If authentication with CozyTouch auth server is
                # valid, but token is invalid for Overkiz API
                # server, the hardware is not supported.
                if user_input[CONF_HUB] in {
                    Server.ATLANTIC_COZYTOUCH,
                    Server.SAUTER_COZYTOUCH,
                    Server.THERMOR_COZYTOUCH,
                } and not isinstance(exception, CozyTouchBadCredentialsError):
                    description_placeholders["unsupported_device"] = "CozyTouch"
                    errors["base"] = "unsupported_hardware"
                else:
                    errors["base"] = "invalid_auth"
            except TimeoutError, ClientError:
                errors["base"] = "cannot_connect"
            except MaintenanceError:
                errors["base"] = "server_in_maintenance"
            except TooManyAttemptsBannedError:
                errors["base"] = "too_many_attempts"
            except UnknownUserError:
                # If the user has no supported CozyTouch devices on
                # the Overkiz API server. Login will return unknown user.
                if user_input[CONF_HUB] in {
                    Server.ATLANTIC_COZYTOUCH,
                    Server.SAUTER_COZYTOUCH,
                    Server.THERMOR_COZYTOUCH,
                }:
                    description_placeholders["unsupported_device"] = "CozyTouch"
                # Somfy Protect accounts are not supported since they don't use
                # the Overkiz API server. Login will return unknown user.
                elif user_input[CONF_HUB] in {
                    Server.SOMFY_AMERICA,
                    Server.SOMFY_DEVELOPER_MODE,
                    Server.SOMFY_EUROPE,
                    Server.SOMFY_OCEANIA,
                }:
                    description_placeholders["unsupported_device"] = "Somfy Protect"
                # Fallback for other unknown devices
                else:
                    description_placeholders["unsupported_device"] = "Unknown"

                errors["base"] = "unsupported_hardware"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
                LOGGER.exception("Unknown error")
            else:
                return self._async_finish_validated_entry(
                    user_input, title=user_input[CONF_USERNAME]
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
        description_placeholders = {
            "local_api_docs": LOCAL_API_DOCS_URL,
            "token_docs": TOKEN_DOCS_URL,
        }

        if user_input:
            self._host = user_input[CONF_HOST]
            self._verify_ssl = user_input[CONF_VERIFY_SSL]
            user_input[CONF_HUB] = self._server

            try:
                user_input = await self.async_validate_input(user_input)
            except TooManyRequestsError:
                errors["base"] = "too_many_requests"
            except (
                BadCredentialsError,
                NoSuchTokenError,
                NotAuthenticatedError,
            ):
                errors["base"] = "invalid_auth"
            except ClientConnectorCertificateError as exception:
                errors["base"] = "certificate_verify_failed"
                LOGGER.debug(exception)
            except (TimeoutError, ClientError) as exception:
                errors["base"] = "cannot_connect"
                LOGGER.debug(exception)
            except MaintenanceError:
                errors["base"] = "server_in_maintenance"
            except TooManyAttemptsBannedError:
                errors["base"] = "too_many_attempts"
            except UnknownUserError:
                # Somfy Protect accounts are not supported since they don't use
                # the Overkiz API server. Login will return unknown user.
                description_placeholders["unsupported_device"] = "Somfy Protect"
                errors["base"] = "unsupported_hardware"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
                LOGGER.exception("Unknown error")
            else:
                return self._async_finish_validated_entry(
                    user_input, title=user_input[CONF_HOST]
                )

        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                    vol.Required(CONF_TOKEN): str,
                    vol.Required(CONF_VERIFY_SSL, default=self._verify_ssl): bool,
                }
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Resolve the gateway after a successful Rexel OAuth2 authorization."""
        self._rexel_oauth_data = data

        # Gateway discovery uses Bearer-only endpoints, so the client needs just
        # the access token: no login() and no gateway_id yet.
        session = async_create_clientsession(self.hass)
        client = OverkizClient(
            server=Server.REXEL,
            credentials=RexelTokenCredentials(
                access_token=data["token"]["access_token"]
            ),
            session=session,
        )

        try:
            self._rexel_gateways = await client.discover_gateways()
        except TimeoutError, ClientError:
            return self.async_abort(reason="cannot_connect")

        if not self._rexel_gateways:
            return self.async_abort(reason="no_gateways")

        if len(self._rexel_gateways) == 1:
            return await self._async_create_rexel_entry(self._rexel_gateways[0])

        return await self.async_step_select_gateway()

    async def async_step_select_gateway(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a gateway on a multi-gateway Rexel account."""
        if user_input:
            gateway = next(
                candidate
                for candidate in self._rexel_gateways
                if candidate.gateway_id == user_input[CONF_GATEWAY_ID]
            )
            return await self._async_create_rexel_entry(gateway)

        return self.async_show_form(
            step_id="select_gateway",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GATEWAY_ID): vol.In(
                        {
                            candidate.gateway_id: candidate.label
                            or candidate.gateway_id
                            for candidate in self._rexel_gateways
                        }
                    ),
                }
            ),
        )

    async def _async_create_rexel_entry(
        self, gateway: GatewayCandidate
    ) -> ConfigFlowResult:
        """Persist the token bundle and resolved gateway as a config entry."""
        await self.async_set_unique_id(gateway.gateway_id, raise_on_progress=False)

        data = {
            **self._rexel_oauth_data,
            CONF_HUB: Server.REXEL,
            CONF_GATEWAY_ID: gateway.gateway_id,
        }

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="reauth_wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="reconfigure_wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=data
            )

        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=gateway.label or "Rexel", data=data)

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        hostname = discovery_info.hostname
        gateway_id = hostname[8:22]
        self._host = f"gateway-{gateway_id}.local:8443"

        LOGGER.debug("DHCP discovery detected gateway %s", obfuscate_id(gateway_id))
        return await self._process_discovery(gateway_id)

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
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
            return await self._process_discovery(
                gateway_id, updates={CONF_HOST: self._host}
            )

        return await self._process_discovery(gateway_id)

    async def _process_discovery(
        self, gateway_id: str, *, updates: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery of a gateway."""
        await self.async_set_unique_id(gateway_id)
        self._abort_if_unique_id_configured(updates=updates)
        self.context["title_placeholders"] = {"gateway_id": gateway_id}

        return await self.async_step_user()

    def _init_flow_from_entry(
        self, entry_data: Mapping[str, Any], gateway_id: str
    ) -> None:
        """Initialize the flow's state from an existing entry for reauth/reconfigure."""
        self.context["title_placeholders"] = {"gateway_id": gateway_id}
        self._api_type = entry_data.get(CONF_API_TYPE, APIType.CLOUD)
        self._server = entry_data[CONF_HUB]

        if self._api_type == APIType.LOCAL:
            self._host = entry_data[CONF_HOST]
            self._verify_ssl = entry_data[CONF_VERIFY_SSL]
        # Rexel cloud reauth re-runs the OAuth2 flow; there is no stored username.
        elif self._server != Server.REXEL:
            self._user = entry_data[CONF_USERNAME]

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth."""
        self._init_flow_from_entry(entry_data, cast(str, self.unique_id))
        return await self.async_step_user(dict(entry_data))

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        entry = self._get_reconfigure_entry()
        self._init_flow_from_entry(entry.data, cast(str, entry.unique_id))
        return await self.async_step_user(dict(entry.data))
