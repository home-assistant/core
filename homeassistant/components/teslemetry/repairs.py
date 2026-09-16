"""Repairs for the Teslemetry integration."""

import asyncio
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError
from aiopowerwall import PowerwallAuthenticationError, PowerwallError
from bleak.exc import BleakError
import probatio
from tesla_fleet_api.exceptions import (
    BluetoothTimeout,
    BluetoothTransportError,
    PrivateKeyError,
    TeslaFleetError,
    TeslaFleetMessageFaultBusy,
    TeslaFleetMessageFaultInternal,
    TeslaFleetMessageFaultTimeout,
    is_key_rejected,
)
from tesla_fleet_api.router import VehicleRouter

from homeassistant.components.bluetooth import async_scanner_count
from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    FlowType,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntryState,
    ConfigSubentry,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType

from . import TeslemetryConfigEntry, _async_get_rsa_key_pem
from .const import (
    BLE_DISCONNECT_TIMEOUT,
    BLE_HANDSHAKE_TIMEOUT,
    CONF_VIN,
    ISSUE_GATEWAY_NOT_FOUND,
    ISSUE_TYPE_BLE_KEY_REJECTED,
    LOGGER,
    SUBENTRY_TYPE_VEHICLE,
    VEHICLE_ISSUE_LEARN_MORE,
)
from .helpers import (
    PowerwallKeyRejectedError,
    async_verify_local_gateway,
    cloud_energy_site,
)


class VehicleMetadataRepairFlow(RepairsFlow):
    """Handle a repair that clears once the vehicle metadata issue resolves."""

    def __init__(
        self, entry: TeslemetryConfigEntry, vin: str, issue_type: str, vehicle: str
    ) -> None:
        """Create flow."""
        self.entry = entry
        self.vin = vin
        self.issue_type = issue_type
        self.placeholders = {
            "vehicle": vehicle,
            "link": VEHICLE_ISSUE_LEARN_MORE.get(issue_type) or "",
        }

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            coordinator = self.entry.runtime_data.metadata_coordinator
            await coordinator.async_refresh()
            vehicles = (coordinator.data or {}).get("vehicles", {})
            still_present = vehicles.get(self.vin, {}).get("issue") == self.issue_type
            if coordinator.last_update_success and not still_present:
                return self.async_create_entry(data={})
            return self.async_show_form(
                step_id="confirm",
                description_placeholders=self.placeholders,
                errors={"base": "not_resolved"},
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=self.placeholders,
        )


class BluetoothKeyRepairFlow(RepairsFlow):
    """Re-check a rejected Bluetooth key, then hand it to the vehicle's reconfigure flow."""

    def __init__(self, entry_id: str, subentry_id: str) -> None:
        """Create flow."""
        self._entry_id = entry_id
        self._subentry_id = subentry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Check the key with a Bluetooth security handshake and re-approve it if still rejected."""
        if user_input is None:
            return self.async_show_form(step_id="confirm")
        if not async_scanner_count(self.hass, connectable=True):
            return self.async_abort(reason="bluetooth_not_available")
        if (router := self._async_get_router()) is None:
            return self.async_abort(reason="bluetooth_not_loaded")
        # The router's health check also refreshes the device handle the handshake connects with.
        if not await router.is_healthy():
            return self.async_show_form(
                step_id="confirm", errors={"base": "cannot_connect"}
            )
        try:
            async with asyncio.timeout(BLE_HANDSHAKE_TIMEOUT):
                # Call the Bluetooth backend directly so no other backend can answer for it.
                # Vehicle security owns the key whitelist and answers while the vehicle sleeps.
                await router.primary.handshakeVehicleSecurity()
        except (
            TimeoutError,
            BluetoothTimeout,
            BluetoothTransportError,
            # Faults the vehicle asks the caller to retry.
            TeslaFleetMessageFaultBusy,
            TeslaFleetMessageFaultInternal,
            TeslaFleetMessageFaultTimeout,
        ) as err:
            LOGGER.debug("Bluetooth handshake could not reach the vehicle: %s", err)
            return self.async_show_form(
                step_id="confirm", errors={"base": "cannot_connect"}
            )
        except TeslaFleetError as err:
            if not is_key_rejected(err):
                LOGGER.error("Bluetooth handshake failed: %s", err)
                return self.async_show_form(
                    step_id="confirm", errors={"base": "unknown"}
                )
        else:
            return self.async_create_entry(data={})
        # Only a rejected key reaches here.
        return await self._async_reconfigure(router)

    @callback
    def _async_get_router(self) -> VehicleRouter | None:
        """Return the vehicle's running Bluetooth router, if the entry is loaded."""
        entry: TeslemetryConfigEntry | None = self.hass.config_entries.async_get_entry(
            self._entry_id
        )
        if (
            entry is None
            or entry.state is not ConfigEntryState.LOADED
            or (subentry := entry.subentries.get(self._subentry_id)) is None
        ):
            return None
        return next(
            (
                vehicle.api
                for vehicle in entry.runtime_data.vehicles
                if vehicle.vin == subentry.data[CONF_VIN]
                and isinstance(vehicle.api, VehicleRouter)
            ),
            None,
        )

    async def _async_reconfigure(self, router: VehicleRouter) -> RepairsFlowResult:
        """Open the vehicle's reconfigure flow to re-approve the key."""
        # The reconfigure flow opens its own link to the vehicle, so release this one first.
        try:
            async with asyncio.timeout(BLE_DISCONNECT_TIMEOUT):
                await router.primary.disconnect()
        except (BleakError, TeslaFleetError, TimeoutError) as err:
            LOGGER.debug("Error disconnecting Bluetooth before reconfigure: %s", err)
        result = await self.hass.config_entries.subentries.async_init(
            (self._entry_id, SUBENTRY_TYPE_VEHICLE),
            context={"source": SOURCE_RECONFIGURE, "subentry_id": self._subentry_id},
        )
        if result["type"] is FlowResultType.ABORT:
            return self.async_abort(reason=result["reason"])
        # Aborting keeps the issue open until the reconfigure reloads the entry.
        return self.async_abort(
            reason="reconfigure",
            next_flow=(FlowType.CONFIG_SUBENTRIES_FLOW, result["flow_id"]),
        )


class GatewayNotFoundRepairFlow(RepairsFlow):
    """Handle a repair that finds a local Powerwall gateway's current address."""

    def __init__(self, entry_id: str, subentry_id: str) -> None:
        """Create flow."""
        self.entry_id = entry_id
        self.subentry_id = subentry_id
        self._entry: TeslemetryConfigEntry | None = None
        self._subentry: ConfigSubentry | None = None
        self._key_pem = b""
        self._default_host = ""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Look up the gateway's address through the cloud before asking the user."""
        entry: TeslemetryConfigEntry | None = self.hass.config_entries.async_get_entry(
            self.entry_id
        )
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")
        energy_data = next(
            (
                energysite
                for energysite in entry.runtime_data.energysites
                if energysite.subentry_id == self.subentry_id
            ),
            None,
        )
        if energy_data is None or self.subentry_id not in entry.subentries:
            return self.async_abort(reason="entry_not_loaded")
        self._entry = entry
        self._subentry = entry.subentries[self.subentry_id]

        try:
            self._key_pem = await _async_get_rsa_key_pem(self.hass)
        except (OSError, ValueError, PrivateKeyError) as err:
            LOGGER.debug("RSA key load failed: %s", err)
            return self.async_abort(reason="cannot_connect")

        try:
            host = await cloud_energy_site(energy_data.api).find_gateway_address()
        except (ClientError, TeslaFleetError) as err:
            LOGGER.debug("Gateway address lookup failed: %s", err)
            host = None
        errors: dict[str, str] = {}
        if host:
            if (error := await self._async_verify(host)) is None:
                return self._async_save_host(host)
            errors["base"] = error

        self._default_host = host or self._subentry.data[CONF_HOST]
        return self._async_show_host_form(errors)

    async def async_step_host(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Ask for the gateway's address and verify it with the saved password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if (error := await self._async_verify(host)) is None:
                return self._async_save_host(host)
            errors["base"] = error
            self._default_host = host
        return self._async_show_host_form(errors)

    @callback
    def _async_show_host_form(self, errors: dict[str, str]) -> RepairsFlowResult:
        """Show the gateway address form."""
        if TYPE_CHECKING:
            assert self._subentry is not None
        return self.async_show_form(
            step_id="host",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_HOST, default=self._default_host): str}
            ),
            description_placeholders={"site": self._subentry.title},
            errors=errors,
        )

    async def _async_verify(self, host: str) -> str | None:
        """Verify the gateway at host, returning an error key on failure."""
        if TYPE_CHECKING:
            assert self._subentry is not None
        try:
            await async_verify_local_gateway(
                self.hass, host, self._subentry.data[CONF_PASSWORD], self._key_pem
            )
        except PowerwallKeyRejectedError:
            return "key_not_approved"
        except PowerwallAuthenticationError:
            return "invalid_auth"
        except PowerwallError as err:
            LOGGER.debug("Local Powerwall verify failed at %s: %s", host, err)
            return "cannot_connect"
        return None

    @callback
    def _async_save_host(self, host: str) -> RepairsFlowResult:
        """Persist the verified gateway address and reload to restore local control."""
        if TYPE_CHECKING:
            assert self._entry is not None
            assert self._subentry is not None
        self.hass.config_entries.async_update_subentry(
            self._entry, self._subentry, data={**self._subentry.data, CONF_HOST: host}
        )
        self.hass.config_entries.async_schedule_reload(self._entry.entry_id)
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if (
        data is not None
        and data.get("issue_type") == ISSUE_TYPE_BLE_KEY_REJECTED
        and isinstance(entry_id := data.get("entry_id"), str)
        and isinstance(subentry_id := data.get("subentry_id"), str)
        and (entry := hass.config_entries.async_get_entry(entry_id)) is not None
        and subentry_id in entry.subentries
    ):
        return BluetoothKeyRepairFlow(entry_id, subentry_id)
    if (
        data is not None
        and isinstance(entry_id := data.get("entry_id"), str)
        and isinstance(vin := data.get("vin"), str)
        and isinstance(issue_type := data.get("issue_type"), str)
        and isinstance(vehicle := data.get("vehicle"), str)
        and (entry := hass.config_entries.async_get_entry(entry_id)) is not None
        and entry.state is ConfigEntryState.LOADED
    ):
        return VehicleMetadataRepairFlow(entry, vin, issue_type, vehicle)
    if (
        issue_id.startswith(f"{ISSUE_GATEWAY_NOT_FOUND}_")
        and data is not None
        and isinstance(entry_id := data.get("entry_id"), str)
        and isinstance(subentry_id := data.get("subentry_id"), str)
    ):
        return GatewayNotFoundRepairFlow(entry_id, subentry_id)

    return ConfirmRepairFlow()
