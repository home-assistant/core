"""Platform for sensor integration."""  # noqa: EXE002

from __future__ import annotations

import logging
from datetime import timedelta
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import Entity as HAEntity
from homeassistant.helpers.area_registry import async_get as async_get_area_registry
from homeassistant.helpers.restore_state import RestoreEntity
from typing import Any
from homeassistant.core import State

from .alarm_common import async_cancelalarm, async_creatependingalarm
from .const import ALARM_TYPE_MED_ALERT, ALARM_TYPE_MONITORING, DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities."""
    HASSComponent.set_hass(hass)

    async_add_entities([MonitoringAlarm()])
    async_add_entities([SleepingSensor()])
    async_add_entities([SomeoneHomeSensor()])
    async_add_entities([SmokeGroup()])
    async_add_entities([MoistureGroup()])
    async_add_entities([CarbonMonoxideGroup()])
    async_add_entities([DoorGroup()])
    async_add_entities([WindowGroup()])
    async_add_entities([SecurityMotionGroup()])
    async_add_entities([SmartApplianceSensor("smartappliance1")])
    async_add_entities([SmartApplianceSensor("smartappliance2")])
    async_add_entities([SmartApplianceSensor("smartappliance3")])


def checkforlabel(labels, value_to_check) -> bool:
    """Check whether a label is in the list of labels."""

    # Handle potential null or empty values and convert to a clean list
    parsed_labels = [label for label in labels if label] if labels else []

    _LOGGER.debug(parsed_labels)

    # Check if the value is in parsed_labels
    if value_to_check in parsed_labels:
        _LOGGER.debug(f"'{value_to_check}' is in parsed_labels. '{parsed_labels}'")
        return True
    _LOGGER.debug(f"'{value_to_check}' is not in parsed_labels. '{parsed_labels}'")
    return False


async def updateEntity(area_id, state):
    sensor = ENTITY_REGISTRY.get(area_id)
    if sensor:
        sensor.set_state(state)


class HASSComponent:
    """Hasscomponent."""

    # Class-level property to hold the hass instance
    hass_instance = None

    @classmethod
    def set_hass(cls, hass: HomeAssistant) -> None:
        """Set Hass."""
        cls.hass_instance = hass

    @classmethod
    def get_hass(cls):  # noqa: ANN206
        """Get Hass."""
        return cls.hass_instance


class SecurityMotionGroup(BinarySensorEntity, RestoreEntity):
    """Representation of a sensor."""

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device_class of the sensor."""
        return BinarySensorDeviceClass.MOTION

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._state = "off"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Security Motion Group Sensor"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:motion-outline"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        return {"state": self._state}

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        entity_id = "group.security_motion_sensors_group"
        sensor_state = self.hass.states.get(entity_id)

        if sensor_state is not None:
            self._state = sensor_state.state  # type: ignore  # noqa: PGH003
        else:
            sensor_state = "unknown"


class WindowGroup(BinarySensorEntity, RestoreEntity):
    """Representation of a sensor."""

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device_class of the sensor."""
        return None

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._state = "off"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Window Group Sensor"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:door-sliding"

    @property
    def state(self):  # noqa: ANN201
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        entity_id = "group.window_sensors_group"
        sensor_state = self.hass.states.get(entity_id)

        if sensor_state is not None:
            self._state = sensor_state.state  # type: ignore  # noqa: PGH003
        else:
            sensor_state = "unknown"


class DoorGroup(BinarySensorEntity, RestoreEntity):
    """Representation of a sensor."""

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device_class of the sensor."""
        return None

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._state = "off"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Door Group Sensor"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:door"

    @property
    def state(self):  # noqa: ANN201
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        entity_id = "group.door_sensors_group"
        sensor_state = self.hass.states.get(entity_id)

        if sensor_state is not None:
            self._state = sensor_state.state  # type: ignore  # noqa: PGH003
        else:
            sensor_state = "unknown"


class CarbonMonoxideGroup(BinarySensorEntity, RestoreEntity):
    """Representation of a sensor."""

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device_class of the sensor."""
        return None

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._state = "off"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Carbon Monoxide Group Sensor"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:smoke-detector-variant"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        entity_id = "group.carbon_monoxide_sensors_group"
        sensor_state = self.hass.states.get(entity_id)

        if sensor_state is not None:
            self._state = sensor_state.state
        else:
            sensor_state = "unknown"


class MoistureGroup(BinarySensorEntity, RestoreEntity):
    """Representation of a sensor."""

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device_class of the sensor."""
        return None

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._state = "off"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Moisture Group Sensor"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:water"

    @property
    def state(self):  # noqa: ANN201
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        entity_id = "group.moisture_sensors_group"
        sensor_state = self.hass.states.get(entity_id)

        if sensor_state is not None:
            self._state = sensor_state.state  # type: ignore  # noqa: PGH003
        else:
            sensor_state = "unknown"


class SmokeGroup(BinarySensorEntity, RestoreEntity):
    """Representation of a sensor."""

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device_class of the sensor."""
        return None

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._state = "off"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Smoke Group Sensor"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:smoke-detector-variant"

    @property
    def state(self):  # noqa: ANN201
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        entity_id = "group.smokealarm_sensors_group"
        sensor_state = self.hass.states.get(entity_id)

        if sensor_state is not None:
            self._state = sensor_state.state  # type: ignore  # noqa: PGH003
        else:
            sensor_state = "unknown"


class BinaryMedAlertSensor(BinarySensorEntity, RestoreEntity):
    """Representation of a sensor."""

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.hass.bus.async_listen(
                "medical_alert_switch_updated", self._handle_switch_event
            )
        )

    async def _handle_switch_event(self, event):
        self._state = "on" if event.data["is_on"] else "off"
        self.async_write_ha_state()

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device_class of the sensor."""
        return None

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._state = "off"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Medical Alert Sensor"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:ambulance"

    @property
    def state(self):  # noqa: ANN201
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        entity_id = "switch.medicalalertalarm"
        switch_state = self.hass.states.get(entity_id)

        turnOn = self._state == "off" and switch_state.state == "on"
        turnOff = self._state == "on" and switch_state.state == "off"

        self._state = switch_state.state

        if turnOn:
            await async_creatependingalarm(self.hass, ALARM_TYPE_MED_ALERT, None)
        elif turnOff:
            hass = HASSComponent.get_hass()
            await async_cancelalarm(hass)


class MonitoringAlarm(BinarySensorEntity, RestoreEntity):
    """Representation of a sensor."""

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.hass.bus.async_listen(
                "monitoring_alarm_switch_updated", self._handle_switch_event
            )
        )

    async def _handle_switch_event(self, event):
        self._state = "on" if event.data["is_on"] else "off"
        self.async_write_ha_state()

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device_class of the sensor."""
        return None

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._state = "off"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Monitoring Alarm Sensor"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:shield-account-outline"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        entity_id = "switch.monitoringalarm"
        switch_state = self.hass.states.get(entity_id)

        turnOn = self._state == "off" and switch_state.state == "on"
        turnOff = self._state == "on" and switch_state.state == "off"

        self._state = switch_state.state

        if turnOn:
            await async_creatependingalarm(self.hass, ALARM_TYPE_MONITORING, None)
        elif turnOff:
            hass = HASSComponent.get_hass()
            await async_cancelalarm(hass)


class SleepingSensor(BinarySensorEntity, RestoreEntity):
    """Representation of a sensor."""

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.hass.bus.async_listen(
                "sleeping_switch_updated", self._handle_switch_event
            )
        )

    async def _handle_switch_event(self, event):
        self._state = "on" if event.data["is_on"] else "off"
        self.async_write_ha_state()

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._state = "off"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Sleeping Sensor"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "sleeping_sensor"

    @property
    def state(self):  # noqa: ANN201
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:chat-sleep-outline"

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        entity_id = "switch.sleep_mode"

        # Get the state of the entity
        state = self.hass.states.get(entity_id)

        if state is not None:
            # Get the state value (e.g., "on" or "off")
            switch_state = state.state
            _LOGGER.info(f"The state of {entity_id} is: {switch_state}")
            self._state = switch_state
        else:
            self._state = "off"


class SomeoneHomeSensor(BinarySensorEntity, RestoreEntity):
    """Representation of a sensor."""

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    def __init__(self) -> None:
        """Initialize the sensor."""
        self._state = "off"
        _LOGGER.debug("[SomeoneHomeSensor] Initialized with state 'off'")

    async def async_added_to_hass(self):
        # Restore previous state if available
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state is not None:
            self._state = last_state.state
            _LOGGER.debug(
                f"[SomeoneHomeSensor] Restored state to '{self._state}' after restart."
            )
        else:
            _LOGGER.debug(
                "[SomeoneHomeSensor] No previous state found, using default 'off'."
            )
        self.async_on_remove(
            self.hass.bus.async_listen(
                "sleeping_switch_updated", self._handle_switch_event
            )
        )
        _LOGGER.debug("[SomeoneHomeSensor] Added to hass, registering event listener.")
        try:
            self.async_on_remove(
                self.hass.bus.async_listen(
                    "sleeping_switch_updated", self._handle_switch_event
                )
            )
        except Exception as e:
            _LOGGER.error(f"[SomeoneHomeSensor] Error registering event listener: {e}")

    async def _handle_switch_event(self, event):
        self._state = "on" if event.data["is_on"] else "off"
        self.async_write_ha_state()
        try:
            is_on = event.data.get("is_on")
            _LOGGER.debug(f"[SomeoneHomeSensor] Received switch event: is_on={is_on}")
            self._state = "on" if is_on else "off"
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"[SomeoneHomeSensor] Error handling switch event: {e}")

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Someone Home Sensor"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "someone_home_sensor"

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:home-circle-outline"

    def set_state(self, state: bool):
        self._attr_is_on = state
        self.async_write_ha_state()
        try:
            _LOGGER.debug(f"[SomeoneHomeSensor] set_state called with: {state}")
            self._attr_is_on = state
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"[SomeoneHomeSensor] Error in set_state: {e}")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor, with detailed debug logging."""
        try:
            home = 0
            _LOGGER.debug(
                "[SomeoneHomeSensor][update] Starting update. Initial home count: 0"
            )
            for entity_id in self.hass.states.entity_ids("person"):
                try:
                    state = self.hass.states.get(entity_id)
                    _LOGGER.debug(
                        f"[SomeoneHomeSensor][update] Checking person {entity_id}: state={getattr(state, 'state', None)}"
                    )
                    if state and state.state == "home":
                        home += 1
                        _LOGGER.debug(
                            f"[SomeoneHomeSensor][update] {entity_id} is home. Incremented home count: {home}"
                        )
                except Exception as e:
                    _LOGGER.error(
                        f"[SomeoneHomeSensor][update] Error checking person {entity_id}: {e}"
                    )

            entity_id = "group.security_motion_sensors_group"
            try:
                motion_sensor_state = self.hass.states.get(entity_id)
                motion_sensor_state_val = (
                    motion_sensor_state.state
                    if motion_sensor_state is not None
                    else "Unknown"
                )
                _LOGGER.debug(
                    f"[SomeoneHomeSensor][update] Motion sensor group state: {motion_sensor_state_val}"
                )
            except Exception as e:
                _LOGGER.error(
                    f"[SomeoneHomeSensor][update] Error getting motion sensor group state: {e}"
                )
                motion_sensor_state_val = "Unknown"

            if home > 0 or (
                isinstance(motion_sensor_state_val, str)
                and motion_sensor_state_val.lower() == "on"
            ):
                prev_state = self._state
                self._state = "on"
                _LOGGER.debug(
                    f"[SomeoneHomeSensor][update] Someone is home or motion detected. State changed from {prev_state} to 'on'. (home={home}, motion_sensor_state_val={motion_sensor_state_val})"
                )
            else:
                prev_state = self._state
                self._state = "off"
                _LOGGER.debug(
                    f"[SomeoneHomeSensor][update] No one home and no motion. State changed from {prev_state} to 'off'. (home={home}, motion_sensor_state_val={motion_sensor_state_val})"
                )
        except Exception as e:
            _LOGGER.error(f"[SomeoneHomeSensor][update] Error in update: {e}")


class SmartApplianceSensor(BinarySensorEntity, RestoreEntity):
    """Representation of a sensor."""

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    def __init__(self, entityname) -> None:
        """Initialize the sensor."""
        self._state = "off"
        self._name = entityname

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device_class of the sensor."""
        return None

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def state(self):  # noqa: ANN201
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:washing-machine"

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        entity_id = f"switch.{self._name}"

        # Get the state of the entity
        state = self.hass.states.get(entity_id)

        if state is not None:
            # Get the state value (e.g., "on" or "off")
            switch_state = state.state
            _LOGGER.info(f"The state of {entity_id} is: {switch_state}")
            self._state = switch_state
        else:
            _LOGGER.info(f"The state of {entity_id} cannnot be determined")
            self._state = "off"


class InBedSensor(BinarySensorEntity, RestoreEntity):
    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    def __init__(self, area_id: str):
        self._attr_name = f"{area_id} In Bed Sensor"
        self._attr_unique_id = f"{area_id}_in_bed_sensor"
        self._attr_is_on = False
        self._area_id = area_id

    @property
    def is_on(self):
        return self._attr_is_on

    def set_state(self, state: bool):
        self._attr_is_on = state
        self.async_write_ha_state()

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:bed-double-outline"
