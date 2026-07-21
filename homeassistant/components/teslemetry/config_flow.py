"""Config Flow for Teslemetry integration."""

from collections.abc import Mapping
from http import HTTPStatus
import logging
from pathlib import Path
from typing import Any, cast, override

from aiohttp import ClientConnectionError, ClientResponseError
from aiopowerwall import (
    DEFAULT_GATEWAY_HOST,
    PowerwallAuthenticationError,
    PowerwallClient,
    PowerwallError,
)
from tesla_fleet_api.const import (
    AuthorizedClientKeyType,
    AuthorizedClientState,
    AuthorizedClientType,
)
from tesla_fleet_api.exceptions import (
    InvalidToken,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.tesla import EnergySiteRouter
from tesla_fleet_api.teslemetry import Teslemetry
from tesla_fleet_api.teslemetry.energysite import AuthorizedClient, TeslemetryEnergySite
import voluptuous as vol

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import TeslemetryConfigEntry
from .const import (
    CLIENT_ID,
    DOMAIN,
    LOGGER,
    POWERWALL_KEY_FILE,
    SUBENTRY_TYPE_ENERGY_SITE,
)


class PowerwallUnreachableError(Exception):
    """Signal that an energy gateway-relay command returned HTTP 502.

    The Teslemetry API returns 502 Bad Gateway on energy gateway-relay grpc
    commands when the customer's Powerwall gateway is unreachable (for example
    it has dropped off the network). This is a retryable upstream condition,
    distinct from an ordinary API failure.
    """


class PowerwallLookupError(Exception):
    """Signal that the authorized-client lookup failed for a non-retryable reason.

    Distinct from the key simply being absent: the gateway did not return a
    usable client list, so the caller must abort (or keep the user on a
    retryable form) rather than mistake the failure for an unregistered key and
    re-register it, which would reset an already pending or verified key.
    """


def _is_gateway_unreachable(err: TeslaFleetError | ClientResponseError) -> bool:
    """Return whether err is a 502 Bad Gateway from an energy gateway command.

    A bodyless 502 surfaces from tesla-fleet-api as ``ResponseError`` (a
    ``TeslaFleetError`` carrying ``status``); a 502 with a JSON body instead
    surfaces as ``aiohttp.ClientResponseError``. ``status`` is looked up with
    ``getattr`` since a bare ``TeslaFleetError`` is not guaranteed to carry one.
    """
    return getattr(err, "status", None) == HTTPStatus.BAD_GATEWAY


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Teslemetry OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 2

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self.data: dict[str, Any] = {}
        self.uid: str | None = None

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return LOGGER

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types supported by this integration."""
        return {SUBENTRY_TYPE_ENERGY_SITE: EnergySiteSubentryFlowHandler}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(CLIENT_ID, "", name="Teslemetry"),
        )
        return await super().async_step_user()

    @override
    async def async_oauth_create_entry(
        self,
        data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle OAuth completion and create config entry."""
        self.data = data

        # Test the connection with the OAuth token
        errors = await self.async_test_connection(data)
        if errors:
            return self.async_abort(reason="oauth_error")

        await self.async_set_unique_id(self.uid)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="reauth_account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="reconfigure_account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=data
            )
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Teslemetry",
            data=data,
        )

    async def async_test_connection(self, token_data: dict[str, Any]) -> dict[str, str]:
        """Test the connection with OAuth token."""
        access_token = token_data["token"]["access_token"]

        teslemetry = Teslemetry(
            session=async_get_clientsession(self.hass),
            access_token=access_token,
        )

        try:
            metadata = await teslemetry.metadata()
        except InvalidToken:
            return {"base": "invalid_access_token"}
        except SubscriptionRequired:
            return {"base": "subscription_required"}
        except ClientConnectionError:
            return {"base": "cannot_connect"}
        except TeslaFleetError as e:
            LOGGER.error("Teslemetry API error: %s", e)
            return {"base": "unknown"}

        self.uid = metadata["uid"]
        return {}

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth on failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={"name": "Teslemetry"},
            )

        return await super().async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user()


class EnergySiteSubentryFlowHandler(ConfigSubentryFlow):
    """Pair a local Powerwall gateway for TEDAPI v1r command routing.

    Reconfiguring an energy site subentry registers the integration's RSA key
    as an authorized client on the gateway (via the cloud API), walks the user
    through approving it on the Powerwall, then collects the local gateway host
    and password. Once paired, the host/password are stored on the subentry,
    which enables Powerwall-first command routing for that site on the next
    reload.

    The authorized-client key this flow registers is intentionally left on
    the gateway when the Home Assistant config entry/subentry is later
    removed. The same gateway-side authorization may be relied on by other
    consumers that share the credential (such as other integrations), so
    removing this integration's config must not deauthorize a credential
    those other consumers may still be using. tesla-fleet-api does expose
    ``remove_authorized_client``, but it is deliberately not called on
    removal for that reason.
    """

    def __init__(self) -> None:
        """Initialize the energy site subentry flow."""
        self._energy_site: TeslemetryEnergySite | None = None
        self._key_pem: bytes | None = None
        self._public_key_der: bytes = b""
        self._public_key_b64: str = ""
        self._discovered_host: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reject manual creation; energy sites come from the Teslemetry account."""
        return self.async_abort(reason="not_supported")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Look up the site's cloud API and start (or resume) key pairing."""
        subentry = self._get_reconfigure_subentry()
        entry = cast(TeslemetryConfigEntry, self._get_entry())
        # runtime_data (the resolved energy sites) only exists while the entry is
        # loaded; core clears it on unload, so bail out cleanly if it is not.
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")
        energy_data = next(
            (
                energysite
                for energysite in entry.runtime_data.energysites
                if energysite.subentry_id == subentry.subentry_id
            ),
            None,
        )
        if energy_data is None:
            return self.async_abort(reason="cannot_connect")
        self._energy_site = cast(
            TeslemetryEnergySite,
            energy_data.api.secondary
            if isinstance(energy_data.api, EnergySiteRouter)
            else energy_data.api,
        )

        try:
            self._discovered_host = await self._energy_site.find_gateway_address() or ""
        except TeslaFleetError as err:
            LOGGER.debug("Gateway address discovery failed: %s", err)
            self._discovered_host = ""

        path = self.hass.config.path(POWERWALL_KEY_FILE)
        keyholder = Teslemetry(
            session=async_get_clientsession(self.hass), access_token=""
        )
        await keyholder.get_rsa_private_key(path)
        self._key_pem = await self.hass.async_add_executor_job(Path(path).read_bytes)
        self._public_key_der = keyholder.rsa_public_der_pkcs1
        self._public_key_b64 = keyholder.rsa_public_der_pkcs1_b64

        try:
            client = await self._find_authorized_client()
        except PowerwallUnreachableError:
            return self.async_abort(reason="powerwall_unreachable")
        except PowerwallLookupError:
            return self.async_abort(reason="cannot_connect")
        if client is not None:
            # The key is already registered on the gateway. If it is verified,
            # move on to credentials; if it is still pending, resume approval
            # without re-registering it (re-adding would reset a pending key).
            if client.state == AuthorizedClientState.VERIFIED:
                return await self.async_step_credentials()
            return await self.async_step_pair()

        try:
            # Not revoked on removal by design; see the class docstring.
            await self._energy_site.add_authorized_client(
                self._public_key_der,
                description="Home Assistant",
                key_type=AuthorizedClientKeyType.RSA,
                authorized_client_type=AuthorizedClientType.CUSTOMER_MOBILE_APP,
            )
        except ClientResponseError as err:
            if _is_gateway_unreachable(err):
                return self.async_abort(reason="powerwall_unreachable")
            LOGGER.error("Add authorized client failed: %s", err)
            return self.async_abort(reason="cannot_connect")
        except TeslaFleetError as err:
            if _is_gateway_unreachable(err):
                return self.async_abort(reason="powerwall_unreachable")
            LOGGER.error("Add authorized client failed: %s", err)
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_pair()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Check once whether the pending key has been approved on the gateway.

        Advances to credentials if verified; otherwise re-shows this form with
        an error describing what the user still needs to do, so they can
        approve the key and submit again.
        """
        assert self._energy_site is not None
        if user_input is None:
            return self.async_show_form(step_id="pair")

        try:
            client = await self._find_authorized_client()
        except PowerwallUnreachableError:
            return self.async_show_form(
                step_id="pair", errors={"base": "powerwall_unreachable"}
            )
        except PowerwallLookupError:
            return self.async_show_form(
                step_id="pair", errors={"base": "cannot_connect"}
            )

        if client is None:
            return self.async_show_form(
                step_id="pair", errors={"base": "key_not_registered"}
            )
        if client.state == AuthorizedClientState.VERIFIED:
            return await self.async_step_credentials()
        if client.state == AuthorizedClientState.PENDING:
            return self.async_show_form(step_id="pair", errors={"base": "key_pending"})
        return self.async_show_form(
            step_id="pair", errors={"base": "key_pending_verification"}
        )

    async def _find_authorized_client(self) -> AuthorizedClient | None:
        """Return our RSA key's authorized-client entry on the gateway, or None.

        Parsing lives in the library's typed ``find_authorized_clients`` accessor
        (envelope unwrap, null-body handling, ``state`` typing). ``None`` is
        returned only when the gateway answers successfully but our key is not
        among the authorized clients (an explicitly empty list authoritatively
        means "not registered").

        A 502 (gateway unreachable) raises ``PowerwallUnreachableError``; any
        other lookup failure raises ``PowerwallLookupError``. Neither is
        collapsed into ``None`` so the caller never mistakes a failed lookup for
        an absent key and re-registers it.
        """
        assert self._energy_site is not None
        try:
            result = await self._energy_site.find_authorized_clients()
        except (ClientResponseError, TeslaFleetError) as err:
            if _is_gateway_unreachable(err):
                raise PowerwallUnreachableError from err
            LOGGER.debug("find_authorized_clients failed: %s", err)
            raise PowerwallLookupError from err
        return next(
            (
                client
                for client in result.clients
                if client.public_key == self._public_key_b64
            ),
            None,
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect the local gateway host/password and verify the LAN connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            # The Powerwall gateway login accepts only the last 5 characters of
            # the Wi-Fi password printed on the gateway; users routinely enter
            # the full string, so trim it to what the gateway will accept.
            password = user_input[CONF_PASSWORD].strip()[-5:]
            assert self._key_pem is not None
            try:
                async with PowerwallClient(
                    host=host,
                    gateway_password=password,
                    rsa_private_key_pem=self._key_pem,
                    session=async_get_clientsession(self.hass),
                ) as client:
                    await client.connect()
            except PowerwallAuthenticationError:
                errors["base"] = "invalid_password"
            except PowerwallError as err:
                LOGGER.debug("Local Powerwall verify failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                entry = self._get_entry()
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_update_and_abort(
                    entry,
                    self._get_reconfigure_subentry(),
                    data_updates={CONF_HOST: host, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=self._discovered_host or DEFAULT_GATEWAY_HOST,
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
