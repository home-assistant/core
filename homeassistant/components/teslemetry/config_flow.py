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
    CONF_SITE_ID,
    DOMAIN,
    LOGGER,
    POWERWALL_KEY_FILE,
    SUBENTRY_TYPE_ENERGY_SITE,
)
from .models import TeslemetryEnergyData


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


_PENDING_STATES = (AuthorizedClientState.PENDING_VERIFICATION,)


def _cloud_energy_site(energy_data: TeslemetryEnergyData) -> TeslemetryEnergySite:
    """Return the cloud energy-site API for pairing.

    Pairing always talks to the Teslemetry cloud to register the key; when a site
    is already paired its api is an EnergySiteRouter, so unwrap the cloud
    secondary rather than the local Powerwall primary.
    """
    return cast(
        TeslemetryEnergySite,
        energy_data.api.secondary
        if isinstance(energy_data.api, EnergySiteRouter)
        else energy_data.api,
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
        # The entry carries a subentry-change update listener, so the new token
        # data is applied by the listener's reload; use the non-reloading variant
        # to avoid reloading twice (and the paired-reload deprecation warning).
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="reauth_account_mismatch")
            return self.async_update_and_abort(self._get_reauth_entry(), data=data)
        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="reconfigure_account_mismatch")
            return self.async_update_and_abort(self._get_reconfigure_entry(), data=data)
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
        self._site_id: int | None = None
        self._site_name: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Let the user opt an account energy site into local Powerwall control.

        Only battery-capable sites that have not already been added are offered;
        selecting one starts the same key-pairing flow reconfigure uses, ending
        in a new subentry bound to that site.
        """
        entry = cast(TeslemetryConfigEntry, self._get_entry())
        # runtime_data (the resolved energy sites) only exists while the entry is
        # loaded; core clears it on unload, so bail out cleanly if it is not.
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        added_site_ids = {
            subentry.unique_id
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_ENERGY_SITE
        }
        available = {
            str(energy_data.id): energy_data
            for energy_data in entry.runtime_data.energysites
            if energy_data.can_local_control
            and str(energy_data.id) not in added_site_ids
        }
        if not available:
            return self.async_abort(reason="no_energy_sites")

        if user_input is not None:
            energy_data = available[user_input[CONF_SITE_ID]]
            self._site_id = energy_data.id
            self._site_name = energy_data.device.get("name") or "Energy Site"
            await self._prepare_energy_site(_cloud_energy_site(energy_data))
            return await self._async_begin_pairing()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SITE_ID): vol.In(
                        {
                            site_id: energy_data.device.get("name") or site_id
                            for site_id, energy_data in available.items()
                        }
                    )
                }
            ),
        )

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
        await self._prepare_energy_site(_cloud_energy_site(energy_data))
        return await self._async_begin_pairing()

    async def _prepare_energy_site(self, energy_site: TeslemetryEnergySite) -> None:
        """Discover the gateway address and load the integration's RSA key."""
        self._energy_site = energy_site

        try:
            self._discovered_host = await energy_site.find_gateway_address() or ""
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

    async def _async_begin_pairing(self) -> SubentryFlowResult:
        """Resume or begin key pairing based on the key's state on the gateway."""
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
            if client.state == AuthorizedClientState.PENDING_VERIFICATION_TIMEOUT:
                # The approval window expired; offer to request a new one
                # in-place rather than sending the user back to setup.
                return await self.async_step_retry()
            # The typed accessor preserves an unrecognized state verbatim. Such
            # a read is not usable, so treat it as a lookup failure rather than
            # resuming pairing on a state we cannot reason about.
            LOGGER.debug("Unrecognized authorized-client state: %s", client.state)
            return self.async_abort(reason="cannot_connect")

        return await self._register_authorized_client()

    async def _register_authorized_client(self) -> SubentryFlowResult:
        """Push our key to the gateway to open an approval window, then wait.

        Shared by the initial registration and the retry step; re-registering
        requests a fresh approval window and resumes the verification wait.
        """
        assert self._energy_site is not None
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

    async def async_step_retry(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Offer to request a new approval window after the previous one expired.

        On submit, re-registers the key to open a fresh approval window and
        resumes the verification wait, exactly as the first attempt does.
        """
        if user_input is None:
            return self.async_show_form(step_id="retry")
        return await self._register_authorized_client()

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
        if client.state == AuthorizedClientState.PENDING_VERIFICATION:
            return self.async_show_form(step_id="pair", errors={"base": "key_pending"})
        if client.state == AuthorizedClientState.PENDING_VERIFICATION_TIMEOUT:
            # The approval window expired; offer to request a new one in-place
            # rather than re-submitting this form forever.
            return await self.async_step_retry()
        # Only an explicit PENDING_VERIFICATION may claim the approval is still
        # awaiting the user; an unrecognized state is a failed read, and
        # reporting it as pending would trap the user in the form retrying forever.
        LOGGER.debug("Unrecognized authorized-client state: %s", client.state)
        return self.async_show_form(step_id="pair", errors={"base": "cannot_connect"})

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
        except (ClientError, TeslaFleetError) as err:
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

    async def _verify_local_gateway(self, host: str, password: str) -> None:
        """Prove the LAN connection and the RSA key against the gateway.

        ``connect()`` performs the gateway password login; the signed read
        that follows is what an unapproved key actually fails, raising
        ``PowerwallAuthenticationError`` when it does. Any other protocol
        fault is a ``PowerwallFaultError`` and is not a rejected key.
        """
        assert self._key_pem is not None
        assert self._energy_site is not None
        async with PowerwallClient(
            host=host,
            gateway_password=password,
            rsa_private_key_pem=self._key_pem,
            session=async_get_clientsession(self.hass),
        ) as client:
            await client.connect()
            try:
                await client.get_status()
            except PowerwallAuthenticationError as err:
                raise PowerwallKeyRejectedError from err

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
            except PowerwallKeyRejectedError as err:
                LOGGER.debug("Powerwall rejected the signed read: %s", err.__cause__)
                errors["base"] = "key_not_approved"
            except PowerwallAuthenticationError:
                errors["base"] = "invalid_password"
            except PowerwallError as err:
                LOGGER.debug("Local Powerwall verify failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self._async_save_credentials(host, password)

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

    @callback
    def _async_save_credentials(self, host: str, password: str) -> SubentryFlowResult:
        """Persist the verified gateway credentials to the subentry.

        Creates a new subentry bound to the selected site during the add flow, or
        updates the existing one during reconfigure. Either way the parent entry
        reloads (via its update listener) so the site starts routing locally.
        """
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_entry()
            subentry = self._get_reconfigure_subentry()
            if (
                self._async_update(
                    entry,
                    subentry,
                    data_updates={CONF_HOST: host, CONF_PASSWORD: password},
                )
                and not entry.update_listeners
            ):
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        return self.async_create_entry(
            title=self._site_name,
            data={
                CONF_SITE_ID: self._site_id,
                CONF_HOST: host,
                CONF_PASSWORD: password,
            },
            unique_id=str(self._site_id),
        )
