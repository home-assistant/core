from __future__ import annotations
import asyncio
from homeassistant.components.number import NumberEntity, NumberDeviceClass
from homeassistant.components.number.const import NumberMode, PERCENTAGE
from homeassistant.const import UnitOfTime
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.core import callback, HomeAssistant
from .const import (
    DOMAIN,
    DATA_CLIENT,
    DATA_COORDINATORS,
    COORDINATOR_ACCOUNTINFO,
    COORDINATOR_CHARGESESSIONS,
    COORDINATOR_SCHEDULES,
)
from .utils import session_in_progress
from .base import OhmeEntity


async def async_setup_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry, async_add_entities
):
    """Setup switches and configure coordinator."""
    account_id = config_entry.data["email"]

    coordinators = hass.data[DOMAIN][account_id][DATA_COORDINATORS]
    client = hass.data[DOMAIN][account_id][DATA_CLIENT]

    numbers = [
        TargetPercentNumber(
            coordinators[COORDINATOR_CHARGESESSIONS],
            coordinators[COORDINATOR_SCHEDULES],
            hass,
            client,
        ),
        PreconditioningNumber(
            coordinators[COORDINATOR_CHARGESESSIONS],
            coordinators[COORDINATOR_SCHEDULES],
            hass,
            client,
        ),
    ]

    if client.cap_available():
        numbers.append(
            PriceCapNumber(coordinators[COORDINATOR_ACCOUNTINFO], hass, client)
        )

    async_add_entities(numbers, update_before_add=True)


class TargetPercentNumber(OhmeEntity, NumberEntity):
    """Target percentage sensor."""

    _attr_translation_key = "target_percentage"
    _attr_icon = "mdi:battery-heart"
    _attr_device_class = NumberDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, coordinator_schedules, hass: HomeAssistant, client):
        super().__init__(coordinator, hass, client)
        self.coordinator_schedules = coordinator_schedules

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator_schedules.async_add_listener(
                self._handle_coordinator_update, None
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        # If session in progress, update this session, if not update the first schedule
        if session_in_progress(self.hass, self._client.email, self.coordinator.data):
            await self._client.async_apply_session_rule(target_percent=int(value))
            await asyncio.sleep(1)
            await self.coordinator.async_refresh()
        else:
            await self._client.async_update_schedule(target_percent=int(value))
            await asyncio.sleep(1)
            await self.coordinator_schedules.async_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get value from data returned from API by coordinator"""
        # Set with the same logic as reading
        if session_in_progress(self.hass, self._client.email, self.coordinator.data):
            target = round(self.coordinator.data["appliedRule"]["targetPercent"])
        elif self.coordinator_schedules.data:
            target = round(self.coordinator_schedules.data["targetPercent"])

        self._state = target if target > 0 else None

    @property
    def native_value(self):
        return self._state


class PreconditioningNumber(OhmeEntity, NumberEntity):
    """Preconditioning sensor."""

    _attr_translation_key = "preconditioning"
    _attr_icon = "mdi:air-conditioner"
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 0
    _attr_native_step = 5
    _attr_native_max_value = 60

    def __init__(self, coordinator, coordinator_schedules, hass: HomeAssistant, client):
        super().__init__(coordinator, hass, client)
        self.coordinator_schedules = coordinator_schedules

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator_schedules.async_add_listener(
                self._handle_coordinator_update, None
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        # If session in progress, update this session, if not update the first schedule
        if session_in_progress(self.hass, self._client.email, self.coordinator.data):
            if value == 0:
                await self._client.async_apply_session_rule(pre_condition=False)
            else:
                await self._client.async_apply_session_rule(
                    pre_condition=True, pre_condition_length=int(value)
                )
            await asyncio.sleep(1)
            await self.coordinator.async_refresh()
        else:
            if value == 0:
                await self._client.async_update_schedule(pre_condition=False)
            else:
                await self._client.async_update_schedule(
                    pre_condition=True, pre_condition_length=int(value)
                )
            await asyncio.sleep(1)
            await self.coordinator_schedules.async_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get value from data returned from API by coordinator"""
        precondition = None
        # Set with the same logic as reading
        if session_in_progress(self.hass, self._client.email, self.coordinator.data):
            enabled = self.coordinator.data["appliedRule"].get(
                "preconditioningEnabled", False
            )
            precondition = (
                0
                if not enabled
                else self.coordinator.data["appliedRule"].get(
                    "preconditionLengthMins", None
                )
            )
        elif self.coordinator_schedules.data:
            enabled = self.coordinator_schedules.data.get(
                "preconditioningEnabled", False
            )
            precondition = (
                0
                if not enabled
                else self.coordinator_schedules.data.get("preconditionLengthMins", None)
            )

        self._state = precondition

    @property
    def native_value(self):
        return self._state


class PriceCapNumber(OhmeEntity, NumberEntity):
    _attr_translation_key = "price_cap"
    _attr_icon = "mdi:cash"
    _attr_device_class = NumberDeviceClass.MONETARY
    _attr_mode = NumberMode.BOX
    _attr_native_step = 0.1
    _attr_native_min_value = -100
    _attr_native_max_value = 100

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._client.async_change_price_cap(cap=value)

        await asyncio.sleep(1)
        await self.coordinator.async_refresh()

    @property
    def native_unit_of_measurement(self):
        if self.coordinator.data is None:
            return None

        penny_unit = {"GBP": "p", "EUR": "c"}
        currency = self.coordinator.data["userSettings"].get("currencyCode", "XXX")

        return penny_unit.get(currency, f"{currency}/100")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get value from data returned from API by coordinator"""
        if self.coordinator.data is not None:
            try:
                self._state = self.coordinator.data["userSettings"]["chargeSettings"][
                    0
                ]["value"]
            except:
                self._state = None
        self.async_write_ha_state()

    @property
    def native_value(self):
        return self._state
