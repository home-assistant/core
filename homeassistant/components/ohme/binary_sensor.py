"""Platform for binary_sensor."""

from __future__ import annotations
import logging
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.dt import utcnow
from .const import (
    DOMAIN,
    DATA_COORDINATORS,
    DATA_SLOTS,
    COORDINATOR_CHARGESESSIONS,
    COORDINATOR_ADVANCED,
    DATA_CLIENT,
)
from .coordinator import OhmeChargeSessionsCoordinator
from .utils import in_slot
from .base import OhmeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """Setup sensors and configure coordinator."""
    account_id = config_entry.data["email"]
    client = hass.data[DOMAIN][account_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][account_id][DATA_COORDINATORS][
        COORDINATOR_CHARGESESSIONS
    ]
    coordinator_advanced = hass.data[DOMAIN][account_id][DATA_COORDINATORS][
        COORDINATOR_ADVANCED
    ]

    sensors = [
        ConnectedBinarySensor(coordinator, hass, client),
        ChargingBinarySensor(coordinator, hass, client),
        PendingApprovalBinarySensor(coordinator, hass, client),
        CurrentSlotBinarySensor(coordinator, hass, client),
        ChargerOnlineBinarySensor(coordinator_advanced, hass, client),
    ]

    async_add_entities(sensors, update_before_add=True)


class ConnectedBinarySensor(OhmeEntity, BinarySensorEntity):
    """Binary sensor for if car is plugged in."""

    _attr_translation_key = "car_connected"
    _attr_icon = "mdi:ev-plug-type2"
    _attr_device_class = BinarySensorDeviceClass.PLUG

    @property
    def is_on(self) -> bool:
        """Calculate state."""

        if self.coordinator.data is None:
            self._state = False
        else:
            self._state = bool(self.coordinator.data["mode"] != "DISCONNECTED")

        return self._state


class ChargingBinarySensor(OhmeEntity, BinarySensorEntity):
    """Binary sensor for if car is charging."""

    _attr_translation_key = "car_charging"
    _attr_icon = "mdi:battery-charging-100"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(
        self, coordinator: OhmeChargeSessionsCoordinator, hass: HomeAssistant, client
    ):
        super().__init__(coordinator, hass, client)

        # Cache the last power readings
        self._last_reading = None
        self._last_reading_in_slot = False

        # State variables for charge state detection
        self._trigger_count = 0

    @property
    def is_on(self) -> bool:
        """Return state."""

        return self._state

    def _calculate_state(self) -> bool:
        """Some trickery to get the charge state to update quickly."""

        power = self.coordinator.data["power"]["watt"]

        # If no last reading or no batterySoc/power, fallback to power > 0
        if (
            not self._last_reading
            or not self._last_reading["batterySoc"]
            or not self._last_reading["power"]
        ):
            _LOGGER.debug(
                "ChargingBinarySensor: No last reading, defaulting to power > 0"
            )
            return power > 0

        # See if we are in a charge slot now and if we were for the last reading
        in_charge_slot = in_slot(self.coordinator.data)
        lr_in_charge_slot = self._last_reading_in_slot
        # Store this for next time
        self._last_reading_in_slot = in_charge_slot

        # If:
        # - Power has dropped by 40%+ since the last reading
        # - Last reading we were in a charge slot
        # - Now we are not in a charge slot
        # The charge has JUST stopped on the session bounary but the power reading is lagging.
        # This condition makes sure we get the charge state updated on the tick immediately after charge stop.
        lr_power = self._last_reading["power"]["watt"]
        if (
            lr_in_charge_slot
            and not in_charge_slot
            and lr_power > 0
            and power / lr_power < 0.6
        ):
            _LOGGER.debug(
                "ChargingBinarySensor: Power drop on state boundary, assuming not charging"
            )
            self._trigger_count = 0
            return False

        # Failing that, we use the watt hours field to check charge state:
        # - If Wh has positive delta
        # - We have a nonzero power reading
        # We are charging. Using the power reading isn't ideal - eg. quirk of MG ZS in #13, so need to revisit
        wh_delta = (
            self.coordinator.data["batterySoc"]["wh"]
            - self._last_reading["batterySoc"]["wh"]
        )
        trigger_state = wh_delta > 0 and power > 0

        _LOGGER.debug(
            f"ChargingBinarySensor: Reading Wh delta of {wh_delta} and power of {power}w"
        )

        # If state is going upwards, report straight away
        if trigger_state and not self._state:
            _LOGGER.debug(
                "ChargingBinarySensor: Upwards state change, reporting immediately"
            )
            self._trigger_count = 0
            return True

        # If state is going to change (downwards only for now), we want to see 3 consecutive readings of the state having
        # changed before reporting it.
        if self._state != trigger_state:
            _LOGGER.debug(
                "ChargingBinarySensor: Downwards state change, incrementing counter"
            )
            self._trigger_count += 1
            if self._trigger_count > 2:
                _LOGGER.debug(
                    "ChargingBinarySensor: Counter hit, publishing downward state change"
                )
                self._trigger_count = 0
                return trigger_state
        else:
            self._trigger_count = 0

        _LOGGER.debug("ChargingBinarySensor: Returning existing state")

        # State hasn't changed or we haven't seen 3 changed values - return existing state
        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update data."""

        # Don't accept updates if 5s hasnt passed
        # State calculations use deltas that may be unreliable to check if requests are too often
        if self._last_updated and (
            utcnow().timestamp() - self._last_updated.timestamp() < 5
        ):
            _LOGGER.debug("ChargingBinarySensor: State update too soon - suppressing")
            return

        # If we have power info and the car is plugged in, calculate state. Otherwise, false
        if (
            self.coordinator.data
            and self.coordinator.data["power"]
            and self.coordinator.data["mode"] != "DISCONNECTED"
        ):
            self._state = self._calculate_state()
        else:
            self._state = False
            _LOGGER.debug(
                "ChargingBinarySensor: No power data or car disconnected - reporting False"
            )

        self._last_reading = self.coordinator.data
        self._last_updated = utcnow()

        self.async_write_ha_state()


class PendingApprovalBinarySensor(OhmeEntity, BinarySensorEntity):
    """Binary sensor for if a charge is pending approval."""

    _attr_translation_key = "pending_approval"
    _attr_icon = "mdi:alert-decagram"

    @property
    def is_on(self) -> bool:
        if self.coordinator.data is None:
            self._state = False
        else:
            self._state = bool(self.coordinator.data["mode"] == "PENDING_APPROVAL")

        return self._state


class CurrentSlotBinarySensor(OhmeEntity, BinarySensorEntity):
    """Binary sensor for if we are currently in a smart charge slot."""

    _attr_translation_key = "slot_active"
    _attr_icon = "mdi:calendar-check"

    @property
    def extra_state_attributes(self):
        """Attributes of the sensor."""
        now = utcnow()
        slots = self._hass.data[DOMAIN][self._client.email].get(DATA_SLOTS, [])

        return {
            "planned_dispatches": [x for x in slots if not x["end"] or x["end"] > now],
            "completed_dispatches": [x for x in slots if x["end"] < now],
        }

    @property
    def is_on(self) -> bool:
        """Return state."""

        return self._state

    @callback
    def _handle_coordinator_update(self) -> None:
        """Are we in a charge slot? This is a bit slow so we only update on coordinator data update."""
        if self.coordinator.data is None:
            self._state = None
        elif self.coordinator.data["mode"] == "DISCONNECTED":
            self._state = False
        else:
            self._state = in_slot(self.coordinator.data)

        self._last_updated = utcnow()

        self.async_write_ha_state()


class ChargerOnlineBinarySensor(OhmeEntity, BinarySensorEntity):
    """Binary sensor for if charger is online."""

    _attr_translation_key = "charger_online"
    _attr_icon = "mdi:web"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Calculate state."""

        if self.coordinator.data and self.coordinator.data["online"]:
            return True
        elif self.coordinator.data:
            return False
        return None
