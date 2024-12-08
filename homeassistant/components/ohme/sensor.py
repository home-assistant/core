"""Platform for sensor integration."""

from __future__ import annotations

import logging
import math

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import (
    COORDINATOR_ADVANCED,
    COORDINATOR_CHARGESESSIONS,
    DATA_CLIENT,
    DATA_COORDINATORS,
    DATA_SLOTS,
    DOMAIN,
)
from .entity import OhmeEntity
from .utils import next_slot, slot_list, slot_list_str

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors and configure coordinator."""
    account_id = config_entry.data["email"]

    client = hass.data[DOMAIN][account_id][DATA_CLIENT]
    coordinators = hass.data[DOMAIN][account_id][DATA_COORDINATORS]

    coordinator = coordinators[COORDINATOR_CHARGESESSIONS]
    adv_coordinator = coordinators[COORDINATOR_ADVANCED]

    sensors = [
        PowerDrawSensor(coordinator, hass, client),
        CurrentDrawSensor(coordinator, hass, client),
        VoltageSensor(coordinator, hass, client),
        CTSensor(adv_coordinator, hass, client),
        EnergyUsageSensor(coordinator, hass, client),
        NextSlotEndSensor(coordinator, hass, client),
        NextSlotStartSensor(coordinator, hass, client),
        SlotListSensor(coordinator, hass, client),
        BatterySOCSensor(coordinator, hass, client),
    ]

    async_add_entities(sensors, update_before_add=True)


class PowerDrawSensor(OhmeEntity, SensorEntity):
    """Sensor for car power draw."""

    _attr_translation_key = "power_draw"
    _attr_icon = "mdi:ev-station"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER

    @property
    def native_value(self):
        """Get value from data returned from API by coordinator."""
        if self.coordinator.data and self.coordinator.data["power"]:
            return self.coordinator.data["power"]["watt"]
        return 0


class CurrentDrawSensor(OhmeEntity, SensorEntity):
    """Sensor for car power draw."""

    _attr_translation_key = "current_draw"
    _attr_icon = "mdi:current-ac"
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    @property
    def native_value(self):
        """Get value from data returned from API by coordinator."""
        if self.coordinator.data and self.coordinator.data["power"]:
            return self.coordinator.data["power"]["amp"]
        return 0


class VoltageSensor(OhmeEntity, SensorEntity):
    """Sensor for EVSE voltage."""

    _attr_translation_key = "voltage"
    _attr_icon = "mdi:sine-wave"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    @property
    def native_value(self):
        """Get value from data returned from API by coordinator."""
        if self.coordinator.data and self.coordinator.data["power"]:
            return self.coordinator.data["power"]["volt"]
        return None


class CTSensor(OhmeEntity, SensorEntity):
    """Sensor for car power draw."""

    _attr_translation_key = "ct_reading"
    _attr_icon = "mdi:gauge"
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    @property
    def native_value(self):
        """Get value from data returned from API by coordinator."""
        return self.coordinator.data["clampAmps"]


class EnergyUsageSensor(OhmeEntity, SensorEntity):
    """Sensor for total energy usage."""

    _attr_translation_key = "energy"
    _attr_icon = "mdi:lightning-bolt-circle"
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_suggested_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 1
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @callback
    def _handle_coordinator_update(self) -> None:
        # Ensure we have data, then ensure value is going up and above 0
        if self.coordinator.data and self.coordinator.data["batterySoc"]:
            new_state = 0
            try:
                new_state = self.coordinator.data["chargeGraph"]["now"]["y"]
            except KeyError:
                _LOGGER.debug(
                    "EnergyUsageSensor: ChargeGraph reading failed, falling back to batterySoc"
                )
                new_state = self.coordinator.data["batterySoc"]["wh"]

            # Let the state reset to 0, but not drop otherwise
            if not new_state or new_state <= 0:
                _LOGGER.debug("EnergyUsageSensor: Resetting Wh reading to 0")
                self._state = 0
            else:
                # Allow a significant (90%+) drop, even if we dont hit exactly 0
                if (
                    self._state
                    and self._state > 0
                    and new_state > 0
                    and (new_state / self._state) < 0.1
                ):
                    self._state = new_state
                else:
                    self._state = max(0, self._state or 0, new_state)

                _LOGGER.debug("EnergyUsageSensor: New state is %s", self._state)

            self.async_write_ha_state()

    @property
    def native_value(self):
        """Return the state of the entity."""
        return self._state


class NextSlotStartSensor(OhmeEntity, SensorEntity):
    """Sensor for next smart charge slot start time."""

    _attr_translation_key = "next_slot_start"
    _attr_icon = "mdi:clock-star-four-points"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return pre-calculated state."""
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Calculate next timeslot. This is a bit slow so we only update on coordinator data update."""
        if (
            self.coordinator.data is None
            or self.coordinator.data["mode"] == "DISCONNECTED"
        ):
            self._state = None
        else:
            self._state = next_slot(
                self._hass, self._client.email, self.coordinator.data
            )["start"]

        self._last_updated = utcnow()

        self.async_write_ha_state()


class NextSlotEndSensor(OhmeEntity, SensorEntity):
    """Sensor for next smart charge slot end time."""

    _attr_translation_key = "next_slot_end"
    _attr_icon = "mdi:clock-star-four-points-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return pre-calculated state."""
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Calculate next timeslot. This is a bit slow so we only update on coordinator data update."""
        if (
            self.coordinator.data is None
            or self.coordinator.data["mode"] == "DISCONNECTED"
        ):
            self._state = None
        else:
            self._state = next_slot(
                self._hass, self._client.email, self.coordinator.data
            )["end"]

        self._last_updated = utcnow()

        self.async_write_ha_state()


class SlotListSensor(OhmeEntity, SensorEntity):
    """Sensor for next smart charge slot end time."""

    _attr_translation_key = "charge_slots"
    _attr_icon = "mdi:timetable"

    @property
    def native_value(self):
        """Return pre-calculated state."""
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get a list of charge slots."""
        if (
            self.coordinator.data is None
            or self.coordinator.data["mode"] == "DISCONNECTED"
            or self.coordinator.data["mode"] == "FINISHED_CHARGE"
        ):
            self._state = None
        else:
            slots = slot_list(self.coordinator.data)

            # Store slots for external use
            self._hass.data[DOMAIN][self._client.email][DATA_SLOTS] = slots

            # Convert list to text
            self._state = slot_list_str(self._hass, self._client.email, slots)

        self._last_updated = utcnow()
        self.async_write_ha_state()


class BatterySOCSensor(OhmeEntity, SensorEntity):
    """Sensor for car battery SOC."""

    _attr_translation_key = "battery_soc"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_suggested_display_precision = 0

    @property
    def icon(self):
        """Icon of the sensor. Round up to the nearest 10% icon."""
        nearest = math.ceil((self._state or 0) / 10.0) * 10
        if nearest == 0:
            return "mdi:battery-outline"
        if nearest == 100:
            return "mdi:battery"
        return "mdi:battery-" + str(nearest)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get value from data returned from API by coordinator."""
        if (
            self.coordinator.data
            and self.coordinator.data["car"]
            and self.coordinator.data["car"]["batterySoc"]
        ):
            self._state = (
                self.coordinator.data["car"]["batterySoc"]["percent"]
                or self.coordinator.data["batterySoc"]["percent"]
            )

            # Don't allow negatives
            if isinstance(self._state, int) and self._state < 0:
                self._state = 0

            self._last_updated = utcnow()
            self.async_write_ha_state()

    @property
    def native_value(self):
        """Return the state of the entity."""
        return self._state
