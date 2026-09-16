"""Repairs for the Teslemetry integration."""

import asyncio
from typing import Any

from tesla_fleet_api.exceptions import (
    BluetoothTimeout,
    BluetoothTransportError,
    TeslaFleetError,
    is_key_rejected,
)
from tesla_fleet_api.router import VehicleRouter

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    FlowType,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType

from . import TeslemetryConfigEntry
from .const import (
    BLE_PING_TIMEOUT,
    CONF_VIN,
    ISSUE_TYPE_BLE_KEY_REJECTED,
    LOGGER,
    SUBENTRY_TYPE_VEHICLE,
    VEHICLE_ISSUE_LEARN_MORE,
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
        """Ping the vehicle over Bluetooth and re-approve the key if it is still rejected."""
        if user_input is None:
            return self.async_show_form(step_id="confirm")
        if (router := self._async_get_router()) is None:
            return self.async_abort(reason="bluetooth_not_loaded")
        # The router's health check also refreshes the device handle the ping connects with.
        if not await router.is_healthy():
            return self.async_show_form(
                step_id="confirm", errors={"base": "cannot_connect"}
            )
        try:
            async with asyncio.timeout(BLE_PING_TIMEOUT):
                # Bypass the router, whose cloud failover would mask a still rejected key.
                response = await router.primary.ping()
        except (TimeoutError, BluetoothTimeout, BluetoothTransportError) as err:
            LOGGER.debug("Bluetooth ping could not reach the vehicle: %s", err)
            return self.async_show_form(
                step_id="confirm", errors={"base": "cannot_connect"}
            )
        except TeslaFleetError as err:
            if is_key_rejected(err):
                return await self._async_reconfigure()
            LOGGER.error("Bluetooth ping failed: %s", err)
            return self.async_show_form(step_id="confirm", errors={"base": "unknown"})
        if not response["response"]["result"]:
            LOGGER.error("Bluetooth ping failed: %s", response["response"]["reason"])
            return self.async_show_form(step_id="confirm", errors={"base": "unknown"})
        return self.async_create_entry(data={})

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

    async def _async_reconfigure(self) -> RepairsFlowResult:
        """Open the vehicle's reconfigure flow to re-approve the key."""
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

    return ConfirmRepairFlow()
