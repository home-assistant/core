"""Config Flow for Teslemetry integration."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, override

from aiohttp import ClientConnectionError
from bleak.exc import BleakError
from tesla_fleet_api.exceptions import (
    BluetoothTimeout,
    BluetoothTransportError,
    InvalidToken,
    NotOnWhitelistFault,
    SubscriptionRequired,
    TeslaFleetError,
)
from tesla_fleet_api.tesla.vehicle.bluetooth import VehicleBluetooth
from tesla_fleet_api.teslemetry import Teslemetry

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
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT_ID, CONF_VIN, DOMAIN, LOGGER, SUBENTRY_TYPE_VEHICLE
from .helpers import async_get_ble_parent


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
        return {SUBENTRY_TYPE_VEHICLE: VehicleSubentryFlowHandler}

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


class VehicleSubentryFlowHandler(ConfigSubentryFlow):
    """Pair a vehicle's virtual key over Bluetooth for local command routing.

    Reconfiguring a vehicle subentry walks the user through adding the
    integration's virtual key to the vehicle over BLE. Once paired, the BLE
    address is stored on the subentry, which enables Bluetooth-first command
    routing for that vehicle on the next reload.
    """

    def __init__(self) -> None:
        """Initialize the vehicle subentry flow."""
        self._vin: str | None = None
        self._address: str | None = None
        self._vehicle: VehicleBluetooth | None = None
        self._pair_task: asyncio.Task[None] | None = None
        self._pair_error: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reject manual creation; vehicles come from the Teslemetry account."""
        return self.async_abort(reason="not_supported")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start Bluetooth pairing for the selected vehicle."""
        self._vin = self._get_reconfigure_subentry().data[CONF_VIN]
        return await self.async_step_scan()

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Find the vehicle over Bluetooth and connect to it."""
        assert self._vin is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            parent = await async_get_ble_parent(self.hass)
            # The advertised BLE name is a hash of the VIN; match on its prefix.
            expected = parent.get_name(self._vin)[:17]
            device = None
            # The name is only in scan responses, so an AUTO-mode scanner that
            # has not swept recently may not have it cached yet.
            await async_request_active_scan(self.hass)
            for info in async_discovered_service_info(self.hass, connectable=True):
                if info.name and info.name.startswith(expected):
                    device = info.device
                    self._address = info.address
                    break

            if device is None:
                errors["base"] = "device_not_found"
            else:
                # Keep the default keepalive here (unlike command routing): it
                # holds the link through the on-screen key-approval wait so the
                # whitelist reply is not lost to a link-supervision drop.
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
        assert self._vehicle is not None
        try:
            await self._vehicle.handshakeVehicleSecurity()
        except NotOnWhitelistFault:
            return await self.async_step_instructions()
        except TeslaFleetError as err:
            LOGGER.error("Bluetooth security handshake failed: %s", err)
            return await self._async_abort("cannot_connect")
        return await self._async_finish()

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
            assert self._vehicle is not None
            # pair() writes the whitelist op exactly once and confirms completion
            # by reply or key-state polling, so it is never re-sent (which would
            # re-prompt the user). It can take minutes, so run it as a progress
            # task rather than blocking the flow request.
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
            # The link dropped before the key could be confirmed - a transport
            # failure, not the user failing to approve in time.
            LOGGER.debug("Bluetooth transport failed during pairing: %s", err)
            self._pair_error = {"base": "cannot_connect"}
            return self.async_show_progress_done(next_step_id="instructions")
        except (BluetoothTimeout, TimeoutError) as err:
            # The key was sent but the vehicle never confirmed - the user has not
            # approved it yet.
            LOGGER.debug("Bluetooth pairing timed out: %s", err)
            self._pair_error = {"base": "timeout"}
            return self.async_show_progress_done(next_step_id="instructions")
        except TeslaFleetError as err:
            # The vehicle rejected the key (e.g. whitelist full, denied on the
            # screen, or valet mode) - not a timeout the user can wait out.
            LOGGER.error("Bluetooth pairing was rejected: %s", err)
            self._pair_error = {"base": "pair_failed"}
            return self.async_show_progress_done(next_step_id="instructions")
        return self.async_show_progress_done(next_step_id="pair")

    async def _async_finish(self) -> SubentryFlowResult:
        """Persist the paired BLE address and reload the entry."""
        assert self._address is not None
        await self._async_disconnect()
        entry = self._get_entry()
        # Write the address before scheduling the reload: async_schedule_reload
        # starts an eager task that could otherwise run setup before the update
        # lands, leaving the reloaded entry cloud-only.
        result = self.async_update_and_abort(
            entry,
            self._get_reconfigure_subentry(),
            data_updates={CONF_ADDRESS: self._address},
        )
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return result

    async def _async_abort(self, reason: str) -> SubentryFlowResult:
        """Disconnect any open BLE connection and abort the flow."""
        await self._async_disconnect()
        return self.async_abort(reason=reason)

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
