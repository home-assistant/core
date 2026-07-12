"""Config Flow for Teslemetry integration."""

import asyncio
from collections.abc import Mapping
import logging
from pathlib import Path
from typing import Any, cast, override

from aiohttp import ClientConnectionError
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
from tesla_fleet_api.teslemetry import EnergySite, Teslemetry
import voluptuous as vol

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
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
    KEY_PAIRING_POLL_ATTEMPTS,
    KEY_PAIRING_POLL_INTERVAL,
    LOGGER,
    POWERWALL_KEY_FILE,
    SUBENTRY_TYPE_ENERGY_SITE,
)

# Authorized-client states meaning "the gateway has confirmed this key".
# Includes both the enum and its raw int value since the command endpoint's
# response shape for this field is not documented.
_VERIFIED_VALUES: tuple[Any, ...] = (
    AuthorizedClientState.VERIFIED,
    int(AuthorizedClientState.VERIFIED),
)


def _normalize_b64(value: Any) -> str:
    """Strip whitespace from a base64 string; return "" for non-strings."""
    return "".join(value.split()) if isinstance(value, str) else ""


def _iter_clients(payload: Any) -> list[Any]:
    """Find the list of authorized clients inside a command response.

    The exact response shape isn't documented, so this walks common wrapper
    keys before falling back to a depth-first search of nested values.
    """
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, Mapping):
        return []
    for key in ("authorized_clients", "authorizedClients", "clients", "response"):
        if key in payload and (found := _iter_clients(payload[key])):
            return found
    for value in payload.values():
        if isinstance(value, (list, Mapping)) and (found := _iter_clients(value)):
            return found
    return []


def _is_verified(list_response: Any, public_key_b64: str) -> bool:
    """Return True if ``list_response`` contains our key in VERIFIED state."""
    target = _normalize_b64(public_key_b64)
    for client in _iter_clients(list_response):
        if not isinstance(client, Mapping):
            continue
        key = client.get("public_key") or client.get("publicKey") or ""
        if _normalize_b64(key) != target:
            continue
        state = client.get("state") or client.get("authorized_client_state")
        return state in _VERIFIED_VALUES
    return False


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
    """

    def __init__(self) -> None:
        """Initialize the energy site subentry flow."""
        self._energy_site: EnergySite | None = None
        self._key_pem: bytes | None = None
        self._public_key_der: bytes = b""
        self._public_key_b64: str = ""

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
        self._energy_site = (
            energy_data.api.secondary
            if isinstance(energy_data.api, EnergySiteRouter)
            else energy_data.api
        )

        path = self.hass.config.path(POWERWALL_KEY_FILE)
        keyholder = Teslemetry(
            session=async_get_clientsession(self.hass), access_token=""
        )
        await keyholder.get_rsa_private_key(path)
        self._key_pem = await self.hass.async_add_executor_job(Path(path).read_bytes)
        self._public_key_der = keyholder.rsa_public_der_pkcs1
        self._public_key_b64 = keyholder.rsa_public_der_pkcs1_b64

        try:
            response = await self._energy_site.list_authorized_clients()
        except TeslaFleetError as err:
            LOGGER.debug("list_authorized_clients failed: %s", err)
            response = None

        if _is_verified(response, self._public_key_b64):
            return await self.async_step_credentials()

        try:
            await self._energy_site.add_authorized_client(
                self._public_key_der,
                description="Home Assistant",
                key_type=AuthorizedClientKeyType.RSA,
                authorized_client_type=AuthorizedClientType.CUSTOMER_MOBILE_APP,
            )
        except TeslaFleetError as err:
            LOGGER.error("Add authorized client failed: %s", err)
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_pair()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Ask the user to approve the pending key, then poll for VERIFIED."""
        assert self._energy_site is not None
        if user_input is None:
            return self.async_show_form(step_id="pair")

        for _ in range(KEY_PAIRING_POLL_ATTEMPTS):
            try:
                response = await self._energy_site.list_authorized_clients()
            except TeslaFleetError:
                response = None
            if _is_verified(response, self._public_key_b64):
                return await self.async_step_credentials()
            await asyncio.sleep(KEY_PAIRING_POLL_INTERVAL)

        return self.async_show_form(step_id="pair", errors={"base": "timeout"})

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
                    vol.Required(CONF_HOST, default=DEFAULT_GATEWAY_HOST): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
