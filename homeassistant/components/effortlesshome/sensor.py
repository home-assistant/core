"""Platform for sensor integration."""

from __future__ import annotations

import logging
import os
import json
from typing import Optional, List
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg


from .const import DOMAIN, NAME
from .notificationdevice import effortlesshomenotificationdevice

from .virtualpowersensor import (
    VirtualPowerSensor,
    VirtualPowerSensorAlwaysOn,
    FakeDeviceVirtualPowerSensor,
    TotalEnergySensor,
)

from .personsensor import eh_personSensor

from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities."""

    async_add_entities([AlarmIDSensor()])
    async_add_entities([AlarmCreateMessageSensor()])
    async_add_entities([AlarmOwnerIDSensor()])
    async_add_entities([AlarmStatusSensor()])
    async_add_entities([AlarmLastEventSensor()])
    async_add_entities([AverageHumiditySensor()])
    async_add_entities([AverageTemperatureSensor()])
    async_add_entities([VirtualIlluminanceSensor()])
    async_add_entities([HighTemperatureTomorrowSensor()])

    async_add_entities(
        [
            ConfigSensor(
                "DaysHistoryToKeep", hass.data[DOMAIN]["DaysHistoryToKeep"]
            )
        ]
    )
    async_add_entities(
        [
            ConfigSensor(
                "LowTemperature", hass.data[DOMAIN]["LowTemperatureWarning"]
            )
        ]
    )
    async_add_entities(
        [
            ConfigSensor(
                "HighTemperature", hass.data[DOMAIN]["HighTemperatureWarning"]
            )
        ]
    )
    async_add_entities(
        [ConfigSensor("LowHumidity", hass.data[DOMAIN]["LowHumidityWarning"])]
    )
    async_add_entities(
        [ConfigSensor("HighHumidity", hass.data[DOMAIN]["HighHumidityWarning"])]
    )

    persons = hass.data.get(DOMAIN, {}).get("persons", [])
    for person in persons:
        async_add_entities([person])
    
    powerentities = []

    entity_registry = er.async_get(hass)
    all_entities = entity_registry.entities.values()

    device_data = hass.states.get(
        DOMAIN +".virtualpowerentities"
    )

    if device_data is not None:
        for entry in device_data:
            for entity in all_entities:
                if entity.entity_id == entry["entity_id"]:
                    _LOGGER.debug(
                        "Adding virtual device: %s with wattage: %s",
                        entry["powersensorname"],
                        entry["wattage"],
                    )
                    virtual_sensor = VirtualPowerSensor(
                        hass, entry["entity_id"], entry["wattage"]
                    )
                    powerentities.append(virtual_sensor)

    device_data = hass.states.get(
        DOMAIN +".virtualdevices"
    )

    if device_data is not None:
        for entry in device_data:
            name = entry["name"]
            wattage = entry["wattage"]
            _LOGGER.debug("Adding virtual device: %s with wattage: %s", name, wattage)
            powerentities.append(VirtualPowerSensorAlwaysOn(hass, name, wattage))

    async_add_entities(powerentities)
    async_add_entities([TotalEnergySensor(hass)])

async def _load_virtual_devices(hass, file_path):
    def read_file():
        with open(file_path, "r") as f:
            return json.load(f)

    return await hass.async_add_executor_job(read_file)

class AlarmIDSensor(SensorEntity, RestoreEntity):
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
        self._state = ""

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "alarm_id_sensor"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Alarm ID Sensor"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:alarm-light-outline"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            self._state = self.hass.data[DOMAIN]["alarm_id"]
        except:
            self._state = ""

class AlarmCreateMessageSensor(SensorEntity, RestoreEntity):
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
        self._state = ""

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Alarm ID Sensor"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:alarm-light-outline"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        try:
            self._state = self.hass.data[DOMAIN]["alarmcreatemessage"]
        except:
            self._state = ""

class AlarmOwnerIDSensor(SensorEntity, RestoreEntity):
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
        self._state = ""

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Alarm Owner ID Sensor"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:shield-moon-outline"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        try:
            self._state = self.hass.data[DOMAIN]["alarmownerid"]
        except:
            self._state = ""


class AlarmStatusSensor(SensorEntity, RestoreEntity):
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
        self._state = ""

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Alarm Status Sensor"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:alarm-light-outline"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            self._state = self.hass.data[DOMAIN]["alarmstatus"]
        except:
            self._state = ""


class AlarmLastEventSensor(SensorEntity, RestoreEntity):
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
        self._state = ""

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Alarm Last Event Sensor"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:alarm-light-outline"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        try:
            self._state = self.hass.data[DOMAIN]["alarmlasteventtype"]
        except:
            self._state = ""


class AverageHumiditySensor(SensorEntity, RestoreEntity):
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
        self._state = ""

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Average Humidity Sensor"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:cloud-percent-outline"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        group_entity_id = "group.humidity_sensors_group"

        # Ensure the group exists
        group_state = self.hass.states.get(group_entity_id)
        if not group_state:
            _LOGGER.debug(f"Group {group_entity_id} not found.")
            return

        # Get all entities in the group
        group_entities = group_state.attributes.get("entity_id", [])

        # Get all entities in the group
        group_entities = group_state.attributes.get("entity_id", [])

        numeric_values = []
        for entity_id in group_entities:
            entity_state = self.hass.states.get(entity_id)
            if entity_state:
                current_state = entity_state.state
                try:
                    # Attempt to convert the state to a float
                    numeric_value = float(current_state)
                    numeric_values.append(numeric_value)
                    _LOGGER.debug(
                        f"Entity {entity_id} has a numeric state of {numeric_value}"
                    )
                except ValueError:
                    # Non-numeric state, skip
                    _LOGGER.debug(
                        f"Entity {entity_id} state '{current_state}' is not numeric."
                    )
            else:
                _LOGGER.warning(f"Entity {entity_id} has no state available.")

        # Calculate the average if we have numeric values
        if numeric_values:
            average_value = sum(numeric_values) / len(numeric_values)
            self._state = round(average_value, 1)
            _LOGGER.debug(
                f"Average numeric state for group {group_entity_id}: {average_value}"
            )
        else:
            _LOGGER.debug(
                f"No numeric values found for entities in group {group_entity_id}."
            )
            self._state = -1


class AverageTemperatureSensor(SensorEntity, RestoreEntity):
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
        self._state = ""

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Average Temperature Sensor"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:thermometer"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        group_entity_id = "group.temperature_sensors_group"

        # Ensure the group exists
        group_state = self.hass.states.get(group_entity_id)
        if not group_state:
            _LOGGER.debug(f"Group {group_entity_id} not found.")
            return

        # Get all entities in the group
        group_entities = group_state.attributes.get("entity_id", [])

        numeric_values = []
        for entity_id in group_entities:
            entity_state = self.hass.states.get(entity_id)
            if entity_state:
                current_state = entity_state.state
                try:
                    # Attempt to convert the state to a float
                    numeric_value = float(current_state)
                    numeric_values.append(numeric_value)
                    _LOGGER.debug(
                        f"Entity {entity_id} has a numeric state of {numeric_value}"
                    )
                except ValueError:
                    # Non-numeric state, skip
                    _LOGGER.debug(
                        f"Entity {entity_id} state '{current_state}' is not numeric."
                    )
            else:
                _LOGGER.warning(f"Entity {entity_id} has no state available.")

        # Calculate the average if we have numeric values
        if numeric_values:
            average_value = sum(numeric_values) / len(numeric_values)
            self._state = round(average_value, 1)
            _LOGGER.debug(
                f"Average numeric state for group {group_entity_id}: {average_value}"
            )
        else:
            _LOGGER.debug(
                f"No numeric values found for entities in group {group_entity_id}."
            )
            self._state = -1


class VirtualIlluminanceSensor(SensorEntity, RestoreEntity):
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
        self._state = 1000

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "VirtualIlluminanceSensor"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:sun-wireless-outline"

    @property
    def device_class(self) -> str:
        """Return the device_class of the sensor."""
        return SensorDeviceClass.ILLUMINANCE

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        _LOGGER.debug("In virtual illuminance sensor update")

        self._state = 200

        sun_state = self.hass.states.get("sun.sun")
        if not sun_state:
            self._state = 1000
            _LOGGER.debug("In virtual illuminance sensor update. sun_state is None.")
            return  # Exit if sun entity isn't available

        if sun_state.state == "below_horizon":
            self._state = 100
            return

        sunrise_time = get_astral_event_date(self.hass, SUN_EVENT_SUNRISE)

        if not sunrise_time:
            self._state = 1000
            _LOGGER.debug("In virtual illuminance sensor update. sunrise time is None.")
            return  # Exit if sunrise time isn't available

        sunset_time = get_astral_event_date(self.hass, SUN_EVENT_SUNSET)

        if not sunset_time:
            self._state = 1000
            _LOGGER.debug("In virtual illuminance sensor update. sunset time is None.")
            return  # Exit if sunrise time isn't available

        # Convert sunrise/set times to datetime and calculate the time difference

        time_since_sunrise = dt_util.now() - sunrise_time
        secondssincesunrise = time_since_sunrise.total_seconds()

        time_until_sunset = sunset_time - dt_util.now()
        secondsuntilsunset = time_until_sunset.total_seconds()

        _LOGGER.debug(
            f"In virtual illuminance sensor seconds since sunrise: {secondssincesunrise}."
        )
        _LOGGER.debug(
            f"In virtual illuminance sensor seconds until sunset: {secondsuntilsunset}."
        )

        # are we closer to sunrise or sunset?
        if secondssincesunrise < secondsuntilsunset:
            if secondssincesunrise <= 500:
                self._state = 200
            elif secondssincesunrise <= 1000:
                self._state = 400
            elif secondssincesunrise <= 1500:
                self._state = 600
            elif secondssincesunrise <= 2000:
                self._state = 800
            else:
                self._state = 1000
        elif secondsuntilsunset <= 500:
            self._state = 200
        elif secondsuntilsunset <= 1000:
            self._state = 400
        elif secondsuntilsunset <= 1500:
            self._state = 600
        elif secondsuntilsunset <= 2000:
            self._state = 800
        else:
            self._state = 1000


class HighTemperatureTomorrowSensor(SensorEntity, RestoreEntity):
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
        self._state = ""

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self.name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "High Temperature Tomorrow Sensor"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:thermometer"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("In high temp tomorrow forecast")

        forecasts = self.hass.services.call(
            "weather",
            "get_forecasts",
            {"type": "daily", "entity_id": "weather.forecast_home"},
            blocking=True,
            return_response=True,
        )

        _LOGGER.debug(f"In high temp tomorrow forecasts: {forecasts}")

        forecast = forecasts.get("weather.forecast_home").get("forecast")

        _LOGGER.debug(f"In high temp tomorrow forecast: {forecast}")

        if len(forecast) > 0:
            self._state = forecast[1]["temperature"]


class ConfigSensor(SensorEntity, RestoreEntity):
    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    def __init__(self, key, state):
        self._key = key
        self._state = state

    @property
    def name(self):
        return f"Config {self._key}"

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"config_sensor_{self._key.lower()}"

    @property
    def device_class(self):
        return None

    @property
    def should_poll(self):
        return False


class eh_person(SensorEntity, RestoreEntity):
    """A persistent, sensor-like representation of an EffortlessHome Person with tracking and notifications."""

    def __init__(self, hass: HomeAssistant, email: str):
        self.hass = hass
        self._email = email
        self._attr_name = email
        self._attr_unique_id = f"effortlesshome_person_{email.lower().replace('@', '_').replace('.', '_')}"
        self._attr_icon = "mdi:account"
        self._attr_should_poll = False

        self._local_tracker_entity_id: Optional[str] = None
        self._remote_tracker_entity_id: Optional[str] = None
        self._notification_devices: List[effortlesshomenotificationdevice] = []

        # Device registry
        self._device_registry = async_get_dev_reg(hass)
        self._device_id = None

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def icon(self) -> str:
        return "mdi:account-group"

    @property
    def state(self) -> str:
        return self._email

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._email

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        return {
            "email": self._email,
            "local_tracker": self._local_tracker_entity_id,
            "remote_tracker": self._remote_tracker_entity_id,
            "notification_devices": [d.unique_id for d in self._notification_devices],
        }

    async def async_set_local_tracker(self, entity_id: str):
        """Link a local device_tracker entity."""
        self._local_tracker_entity_id = entity_id
        _LOGGER.info("[eh_person] Linked local tracker for %s: %s", self._email, entity_id)
        await self.async_update_ha_state()

    async def async_set_remote_tracker(self, entity_id: str):
        """Link a remote (EffortlessHome cloud) device_tracker entity."""
        self._remote_tracker_entity_id = entity_id
        _LOGGER.info("[eh_person] Linked remote tracker for %s: %s", self._email, entity_id)
        await self.async_update_ha_state()

    async def async_set_notification_devices(
        self, hass: HomeAssistant, token: str, device_name: str, platform_name: str
    ):
        """Link a notification device."""
        if not token:
            _LOGGER.warning("[eh_person] Missing token for notification registration.")
            return

        existing = next(
            (d for d in self._notification_devices if d.unique_id == f"effortlesshome_notify_{device_name}"),
            None,
        )
        if existing:
            _LOGGER.info("[eh_person] Notification device %s already exists for %s", token, self._email)
        else:
            device = effortlesshomenotificationdevice(self.hass, token, device_name, platform_name)
            self._notification_devices.append(device)
            _LOGGER.info("[eh_person] Added notification device for %s: %s", self._email, platform_name)
            await self.async_update_ha_state()

    async def async_added_to_hass(self):
        """Handle entity addition and restore previous state."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            attrs = last_state.attributes or {}
            self._local_tracker_entity_id = attrs.get("local_tracker")
            self._remote_tracker_entity_id = attrs.get("remote_tracker")

            restored_devices = attrs.get("notification_devices", [])
            if restored_devices:
                self._notification_devices = [
                    effortlesshomenotificationdevice(self.hass, None, dev_id, "restored")
                    for dev_id in restored_devices
                ]

            _LOGGER.info(
                "[eh_person] Restored state for %s: local=%s remote=%s devices=%s",
                self._email,
                self._local_tracker_entity_id,
                self._remote_tracker_entity_id,
                restored_devices,
            )
        else:
            _LOGGER.info("[eh_person] No previous state to restore for %s", self._email)
