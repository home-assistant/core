"""Config Flow for Teslemetry integration."""

from collections.abc import Mapping
from http import HTTPStatus
import logging
from pathlib import Path
from typing import Any, cast, override

from aiohttp import ClientError
from aiopowerwall import (
    DEFAULT_GATEWAY_HOST,
    PowerwallAuthenticationError,
    PowerwallClient,
    PowerwallEnergySite,
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


class PowerwallKeyRejectedError(Exception):
    """Signal that the gateway refused a v1r-signed read with our RSA key.

    Distinct from a bad gateway password: the login succeeded, but the key has
    not been approved on the gateway, so only signed requests fail.
    """


class PowerwallGatewayMismatchError(Exception):
    """Signal that the local gateway's DIN doesn't match the site's cloud DIN.

    The RSA key is shared by every site, so it authorizes each of the
    account's gateways: without this check a host pointed at the wrong
    gateway would command another site's house.
    """

    def __init__(self, expected: str, actual: str) -> None:
        """Store the mismatched DINs for the caller's abort placeholders."""
        super().__init__(f"expected {expected}, got {actual}")
        self.expected = expected
        self.actual = actual


_PENDING_STATES = (
    AuthorizedClientState.PENDING,
    AuthorizedClientState.PENDING_VERIFICATION,
)


def _is_gateway_unreachable(err: TeslaFleetError | ClientError) -> bool:
    """Return whether err is a 502 Bad Gateway from an energy gateway command.

    A bodyless 502 surfaces from tesla-fleet-api as ``ResponseError`` (a
    ``TeslaFleetError`` carrying ``status``); a 502 with a JSON body instead
    surfaces as ``aiohttp.ClientResponseError``. ``status`` is looked up with
    ``getattr`` since neither a bare ``TeslaFleetError`` nor a transport-level
    ``ClientError`` is guaranteed to carry one.
    """
    return getattr(err, "status", None) == HTTPStatus.BAD_GATEWAY


def _din_matches(expected: str, actual: str) -> bool:
    """Return whether two gateway DINs identify the same gateway.

    Compared normalized: the local gateway's DIN has not been confirmed
    byte-identical to the cloud's, and rejecting a valid pairing over a
    case or whitespace skew would be worse than not comparing at all.
    """
    return expected.strip().casefold() == actual.strip().casefold()


def _authorized_client_from_local(entry: dict[str, Any]) -> AuthorizedClient:
    """Build an ``AuthorizedClient`` from a local ``list_authorized_clients`` entry.

    aiopowerwall normalizes ``public_key``/``state`` to the same keys the
    cloud envelope uses, with ``state`` already the enum member's name (for
    example ``"VERIFIED"``) rather than an int. An unrecognized name is kept
    verbatim rather than dropped, matching the cloud accessor's handling of
    an unrecognized state.
    """
    state = entry["state"]
    try:
        typed_state: AuthorizedClientState | str = AuthorizedClientState[state]
    except KeyError:
        typed_state = state
    return AuthorizedClient(
        public_key=entry["public_key"], state=typed_state, raw=entry
    )


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
        except ClientError:
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
        self._local_energy_site: PowerwallEnergySite | None = None
        self._key_pem: bytes | None = None
        self._public_key_der: bytes = b""
        self._public_key_b64: str = ""
        self._discovered_host: str = ""
        self._gateway_id: str | None = None

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
        if isinstance(energy_data.api, EnergySiteRouter):
            self._energy_site = cast(TeslemetryEnergySite, energy_data.api.secondary)
            self._local_energy_site = cast(PowerwallEnergySite, energy_data.api.primary)
        else:
            self._energy_site = cast(TeslemetryEnergySite, energy_data.api)
            self._local_energy_site = None
        self._gateway_id = energy_data.gateway_id

        try:
            self._discovered_host = await self._energy_site.find_gateway_address() or ""
        except (ClientError, TeslaFleetError) as err:
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
            if client.state in _PENDING_STATES:
                return await self.async_step_pair()
            # The typed accessor preserves an unrecognized state verbatim. Such
            # a read is not usable, so treat it as a lookup failure rather than
            # resuming pairing on a state we cannot reason about.
            LOGGER.debug("Unrecognized authorized-client state: %s", client.state)
            return self.async_abort(reason="cannot_connect")

        try:
            # Not revoked on removal by design; see the class docstring.
            LOGGER.info("Powerwall key setup: id=%s", self._energy_site.energy_site_id)
            await self._energy_site.add_authorized_client(
                self._public_key_der,
                description="Home Assistant",
                key_type=AuthorizedClientKeyType.RSA,
                authorized_client_type=AuthorizedClientType.CUSTOMER_MOBILE_APP,
            )
        except (ClientError, TeslaFleetError) as err:
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
        if client.state == AuthorizedClientState.PENDING_VERIFICATION:
            return self.async_show_form(
                step_id="pair", errors={"base": "key_pending_verification"}
            )
        # Only an explicit PENDING_VERIFICATION may claim the approval is still
        # being verified; an unrecognized state is a failed read, and reporting
        # it as pending would trap the user in the form retrying forever.
        LOGGER.debug("Unrecognized authorized-client state: %s", client.state)
        return self.async_show_form(step_id="pair", errors={"base": "cannot_connect"})

    async def _find_authorized_client(self) -> AuthorizedClient | None:
        """Return our RSA key's authorized-client entry on the gateway, or None.

        Reads the gateway directly over the LAN when the site is already
        paired for local control - the authoritative source for whether a key
        can make signed local requests, and the one that works whether or not
        Teslemetry's cloud proxy is behaving. Only queries the cloud when
        there is no local key to read from yet (the site is not paired).
        ``None`` is returned only when the gateway answers successfully but
        our key is not among the authorized clients (an explicitly empty list
        authoritatively means "not registered").

        A 502 from the cloud path raises ``PowerwallUnreachableError``; any
        other lookup failure (cloud or local) raises ``PowerwallLookupError``.
        Neither is collapsed into ``None`` so the caller never mistakes a
        failed lookup for an absent key and re-registers it.
        """
        assert self._energy_site is not None
        if self._local_energy_site is not None:
            try:
                payload = await self._local_energy_site.list_authorized_clients()
            except PowerwallError as err:
                LOGGER.debug("local list_authorized_clients failed: %s", err)
                raise PowerwallLookupError from err
            clients = [
                _authorized_client_from_local(entry)
                for entry in payload["response"]["clients"]
            ]
        else:
            try:
                result = await self._energy_site.find_authorized_clients()
            except (ClientError, TeslaFleetError) as err:
                if _is_gateway_unreachable(err):
                    raise PowerwallUnreachableError from err
                LOGGER.debug("find_authorized_clients failed: %s", err)
                raise PowerwallLookupError from err
            clients = result.clients
        return next(
            (client for client in clients if client.public_key == self._public_key_b64),
            None,
        )

    async def _verify_local_gateway(self, host: str, password: str) -> str:
        """Prove the LAN connection and the RSA key, returning the gateway DIN.

        ``connect()`` only performs the gateway password login and fetches the
        DIN over an unsigned endpoint, so it succeeds even when the gateway has
        not approved our key. The DIN is checked against the site's cloud
        gateway ID before the signed read that follows, so a host pointed at
        the wrong gateway is rejected without issuing a signed request against
        it. The signed read is what an unapproved key actually fails, and it
        raises ``PowerwallAuthenticationError`` when it does; any other
        protocol fault is a ``PowerwallFaultError`` and is not a rejected key.
        """
        assert self._key_pem is not None
        assert self._energy_site is not None
        async with PowerwallClient(
            host=host,
            gateway_password=password,
            rsa_private_key_pem=self._key_pem,
            session=async_get_clientsession(self.hass),
        ) as client:
            din = await client.connect()
            if self._gateway_id is None:
                # Pairing proceeds: refusing over a missing comparand would
                # block a valid gateway. Warn so a skipped identity check is
                # never silent.
                LOGGER.warning(
                    "Energy site %s reports no gateway ID, so %s cannot be "
                    "confirmed as this site's own gateway; pairing anyway",
                    self._energy_site.energy_site_id,
                    din,
                )
            elif not _din_matches(self._gateway_id, din):
                raise PowerwallGatewayMismatchError(self._gateway_id, din)
            try:
                await client.get_status()
            except PowerwallAuthenticationError as err:
                raise PowerwallKeyRejectedError from err
            return din

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect the local gateway host/password and verify the LAN connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            assert self._energy_site is not None
            host = user_input[CONF_HOST].strip()
            # The Powerwall gateway login accepts only the last 5 characters of
            # the Wi-Fi password printed on the gateway; users routinely enter
            # the full string, so trim it to what the gateway will accept.
            password = user_input[CONF_PASSWORD].strip()[-5:]
            try:
                await self._verify_local_gateway(host, password)
            except PowerwallGatewayMismatchError as err:
                return self.async_abort(
                    reason="gateway_mismatch",
                    description_placeholders={
                        "expected": err.expected,
                        "actual": err.actual,
                    },
                )
            except PowerwallKeyRejectedError as err:
                LOGGER.debug("Powerwall rejected the signed read: %s", err.__cause__)
                errors["base"] = "key_not_approved"
            except PowerwallAuthenticationError:
                errors["base"] = "invalid_password"
            except PowerwallError as err:
                LOGGER.debug("Local Powerwall verify failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_entry(),
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
