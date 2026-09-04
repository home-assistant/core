"""Config Flow for Teslemetry integration."""

import asyncio
from collections.abc import Mapping
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast, override

from aiohttp import ClientError
from aiopowerwall import (
    DEFAULT_GATEWAY_HOST,
    PowerwallAuthenticationError,
    PowerwallClient,
    PowerwallError,
)
from bleak.exc import BleakError
from tesla_fleet_api.const import (
    AuthorizedClientKeyType,
    AuthorizedClientState,
    AuthorizedClientType,
)
from tesla_fleet_api.exceptions import (
    BluetoothTimeout,
    BluetoothTransportError,
    InvalidToken,
    NotOnWhitelistFault,
    SubscriptionRequired,
    TeslaFleetError,
    WhitelistOperationAttemptingToAddExistingKey,
)
from tesla_fleet_api.tesla.vehicle.bluetooth import VehicleBluetooth
from tesla_fleet_api.teslemetry import Teslemetry
from tesla_fleet_api.teslemetry.energysite import AuthorizedClient, TeslemetryEnergySite
import voluptuous as vol

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.bluetooth import (
    async_discovered_service_info,
    async_request_active_scan,
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
from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import _BLE_KEY_ERRORS, TeslemetryConfigEntry
from .const import (
    CLIENT_ID,
    CONF_SITE_ID,
    CONF_VIN,
    DOMAIN,
    LOGGER,
    POWERWALL_KEY_FILE,
    SUBENTRY_TYPE_ENERGY_SITE,
    SUBENTRY_TYPE_VEHICLE,
)
from .helpers import async_get_ble_parent


class PowerwallLookupError(Exception):
    """Signal that the authorized-client lookup failed for a non-retryable reason."""


class PowerwallKeyRejectedError(Exception):
    """Signal that the gateway refused a v1r-signed read with our RSA key."""


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
        return {
            SUBENTRY_TYPE_VEHICLE: VehicleSubentryFlowHandler,
            SUBENTRY_TYPE_ENERGY_SITE: EnergySiteSubentryFlowHandler,
        }

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
            return self._async_apply_token(self._get_reauth_entry(), data)
        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="reconfigure_account_mismatch")
            return self._async_apply_token(self._get_reconfigure_entry(), data)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Teslemetry",
            data=data,
        )

    def _async_apply_token(
        self, entry: ConfigEntry, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Store the refreshed token and reload the entry exactly once."""
        if entry.state is not ConfigEntryState.LOADED:
            # Unloaded entries have no update listener, so no paired-reload warning.
            return self.async_update_reload_and_abort(entry, data=data)
        # Reload manually: async_update_reload_and_abort would warn (listener present).
        result = self.async_update_and_abort(entry, data=data)
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return result

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


class VehicleSubentryFlowHandler(ConfigSubentryFlow):
    """Add local Bluetooth control to one of the account's vehicles."""

    def __init__(self) -> None:
        """Initialize the vehicle subentry flow."""
        self._vin: str | None = None
        self._title: str | None = None
        self._address: str | None = None
        self._vehicle: VehicleBluetooth | None = None
        self._pair_task: asyncio.Task[None] | None = None
        self._pair_error: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select an account vehicle to add over Bluetooth, then pair it."""
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")
        already_added = {
            subentry.data[CONF_VIN]
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)
            if CONF_VIN in subentry.data
        }
        # A paired vehicle reuses the existing device, so no new device is created here.
        choices = {
            vehicle.vin: vehicle.device["name"] or vehicle.vin
            for vehicle in entry.runtime_data.vehicles
            if vehicle.vin not in already_added
        }
        if not choices:
            return self.async_abort(reason="no_vehicles")

        if user_input is not None:
            self._vin = user_input[CONF_VIN]
            self._title = choices[self._vin]
            return await self.async_step_scan()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIN): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=vin, label=name)
                                for vin, name in choices.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Find the vehicle over Bluetooth and connect to it."""
        if TYPE_CHECKING:
            assert self._vin is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                parent = await async_get_ble_parent(self.hass)
            except _BLE_KEY_ERRORS as err:
                LOGGER.debug("Bluetooth key load failed: %s", err)
                return self.async_abort(reason="cannot_connect")
            # The advertised BLE name is a hash of the VIN; match on its prefix.
            expected = parent.get_name(self._vin)[:17]
            device = None
            # The name is only in scan responses, so an active scan may be needed to see it.
            await async_request_active_scan(self.hass)
            for info in async_discovered_service_info(self.hass, connectable=True):
                if info.name and info.name.startswith(expected):
                    device = info.device
                    self._address = info.address
                    break

            if device is None:
                errors["base"] = "device_not_found"
            else:
                # Keep the default keepalive (unlike command routing) so the link survives the on-screen key-approval wait.
                self._vehicle = parent.vehicles.createBluetooth(
                    self._vin, device=device
                )
                try:
                    await self._vehicle.connect()
                except (BleakError, TeslaFleetError, TimeoutError) as err:
                    LOGGER.error("Failed to connect over Bluetooth: %s", err)
                    await self._async_disconnect()
                    errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_pair()

        return self.async_show_form(
            step_id="scan",
            errors=errors,
            description_placeholders={"vin": self._vin},
        )

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Check whether the virtual key is already whitelisted on the vehicle."""
        if TYPE_CHECKING:
            assert self._vehicle is not None
        try:
            await self._vehicle.handshakeVehicleSecurity()
        except NotOnWhitelistFault:
            return await self.async_step_instructions()
        except (BleakError, TeslaFleetError, TimeoutError) as err:
            LOGGER.error("Bluetooth security handshake failed: %s", err)
            await self._async_disconnect()
            return self.async_abort(reason="cannot_connect")
        if TYPE_CHECKING:
            assert self._address is not None
            assert self._vin is not None
        await self._async_disconnect()
        return self.async_create_entry(
            title=self._title or self._vin,
            data={CONF_VIN: self._vin, CONF_ADDRESS: self._address},
            unique_id=self._vin,
        )

    async def async_step_instructions(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Ask the user to approve the virtual key on the vehicle touchscreen."""
        if user_input is not None:
            return await self.async_step_authorize()
        errors = self._pair_error
        self._pair_error = {}
        return self.async_show_form(
            step_id="instructions",
            errors=errors,
            description_placeholders={"vin": self._vin or ""},
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add the virtual key to the vehicle while showing pairing progress."""
        if self._pair_task is None:
            if TYPE_CHECKING:
                assert self._vehicle is not None
            # pair() can take minutes, so run it as a progress task rather than blocking the flow.
            self._pair_task = self.hass.async_create_task(self._vehicle.pair())

        if not self._pair_task.done():
            return self.async_show_progress(
                step_id="authorize",
                progress_action="pair",
                progress_task=self._pair_task,
                description_placeholders={"vin": self._vin or ""},
            )

        task = self._pair_task
        self._pair_task = None
        try:
            task.result()
        except (BluetoothTransportError, BleakError) as err:
            # Transport failure (link dropped), not the user failing to approve in time.
            LOGGER.debug("Bluetooth transport failed during pairing: %s", err)
            self._pair_error = {"base": "cannot_connect"}
            return self.async_show_progress_done(next_step_id="instructions")
        except (BluetoothTimeout, TimeoutError) as err:
            # The key was sent but never confirmed - the user has not approved it yet.
            LOGGER.debug("Bluetooth pairing timed out: %s", err)
            self._pair_error = {"base": "timeout"}
            return self.async_show_progress_done(next_step_id="instructions")
        except WhitelistOperationAttemptingToAddExistingKey as err:
            # This exception means the key is already whitelisted, so pairing succeeded; fall through to re-handshake.
            LOGGER.debug("Virtual key is already on the whitelist: %s", err)
        except TeslaFleetError as err:
            # The vehicle rejected the key (whitelist full, denied, or valet mode) - not a waitable timeout.
            LOGGER.error("Bluetooth pairing was rejected: %s", err)
            self._pair_error = {"base": "pair_failed"}
            return self.async_show_progress_done(next_step_id="instructions")
        return self.async_show_progress_done(next_step_id="pair")

    async def _async_disconnect(self) -> None:
        """Disconnect the BLE link, if any, and drop the reference to it."""
        vehicle = self._vehicle
        self._vehicle = None
        if vehicle is not None:
            try:
                await vehicle.disconnect()
            except (BleakError, TeslaFleetError, TimeoutError) as err:
                LOGGER.debug("Error disconnecting Bluetooth: %s", err)

    @callback
    @override
    def async_remove(self) -> None:
        """Release resources if the flow is abandoned mid-pairing."""
        if self._pair_task is not None and not self._pair_task.done():
            self._pair_task.cancel()
        if self._vehicle is not None:
            self.hass.async_create_task(self._async_disconnect())


class EnergySiteSubentryFlowHandler(ConfigSubentryFlow):
    """Pair a local Powerwall gateway for TEDAPI v1r command routing."""

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
        """Let the user opt an account energy site into local Powerwall control."""
        entry = cast(TeslemetryConfigEntry, self._get_entry())
        # runtime_data exists only while the entry is loaded; core clears it on unload.
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
            # Only unpaired sites are offered, so api is always the cloud EnergySite.
            if abort := await self._prepare_energy_site(
                cast(TeslemetryEnergySite, energy_data.api)
            ):
                return abort
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

    async def _prepare_energy_site(
        self, energy_site: TeslemetryEnergySite
    ) -> SubentryFlowResult | None:
        """Discover the gateway address and load the integration's RSA key.

        Returns an abort result if the RSA key cannot be loaded, else None.
        """
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
        try:
            await keyholder.get_rsa_private_key(path)
            self._key_pem = await self.hass.async_add_executor_job(
                Path(path).read_bytes
            )
        except (OSError, ValueError) as err:
            LOGGER.debug("RSA key load failed: %s", err)
            return self.async_abort(reason="cannot_connect")
        self._public_key_der = keyholder.rsa_public_der_pkcs1
        self._public_key_b64 = keyholder.rsa_public_der_pkcs1_b64
        return None

    async def _async_begin_pairing(self) -> SubentryFlowResult:
        """Resume or begin key pairing based on the key's state on the gateway."""
        try:
            client = await self._find_authorized_client()
        except PowerwallLookupError:
            return self.async_abort(reason="cannot_connect")
        if client is not None:
            # Key already registered; do not re-register a pending one (it would reset).
            if client.state == AuthorizedClientState.VERIFIED:
                return await self.async_step_credentials()
            if client.state == AuthorizedClientState.PENDING_VERIFICATION:
                return await self.async_step_pair()
            if client.state != AuthorizedClientState.PENDING_VERIFICATION_TIMEOUT:
                # Unrecognized state is unusable; treat it as a lookup failure.
                LOGGER.debug("Unrecognized authorized-client state: %s", client.state)
                return self.async_abort(reason="cannot_connect")
            # Re-registering resets the expired window (no duplicate); fall through.

        if TYPE_CHECKING:
            assert self._energy_site is not None
        try:
            # Not revoked on removal: other consumers may share this key.
            LOGGER.info("Powerwall key setup: id=%s", self._energy_site.energy_site_id)
            await self._energy_site.add_authorized_client(
                self._public_key_der,
                description="Home Assistant",
                key_type=AuthorizedClientKeyType.RSA,
                authorized_client_type=AuthorizedClientType.CUSTOMER_MOBILE_APP,
            )
        except (ClientError, TeslaFleetError) as err:
            LOGGER.error("Add authorized client failed: %s", err)
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_pair()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Check once whether the pending key has been approved on the gateway."""
        if TYPE_CHECKING:
            assert self._energy_site is not None
        if user_input is None:
            return self.async_show_form(step_id="pair")

        try:
            client = await self._find_authorized_client()
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
        # An unrecognized state reported as pending would trap the user forever.
        LOGGER.debug("Unrecognized authorized-client state: %s", client.state)
        return self.async_show_form(step_id="pair", errors={"base": "cannot_connect"})

    async def _find_authorized_client(self) -> AuthorizedClient | None:
        """Return our RSA key's authorized-client entry on the gateway, or None."""
        if TYPE_CHECKING:
            assert self._energy_site is not None
        try:
            result = await self._energy_site.find_authorized_clients()
        except (ClientError, TeslaFleetError) as err:
            # Raise so a failed lookup is not mistaken for an unregistered key.
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
        """Prove the LAN connection and the RSA key against the gateway."""
        if TYPE_CHECKING:
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
                # connect() passed the password, so a failure here is key rejection.
                await client.get_status()
            except PowerwallAuthenticationError as err:
                raise PowerwallKeyRejectedError from err

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect the local gateway host/password and verify the LAN connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if TYPE_CHECKING:
                assert self._energy_site is not None
            host = user_input[CONF_HOST].strip()
            # The gateway accepts only the last 5 characters of the Wi-Fi password.
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
        """Persist the verified gateway credentials to a new subentry."""
        return self.async_create_entry(
            title=self._site_name,
            data={
                CONF_SITE_ID: self._site_id,
                CONF_HOST: host,
                CONF_PASSWORD: password,
            },
            unique_id=str(self._site_id),
        )
