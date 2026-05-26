"""Support for collecting data from the ARWN project."""

import logging
from typing import Any

from arwn_client import parse_message

from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.json import json_loads_object

_LOGGER = logging.getLogger(__name__)

DOMAIN = "arwn"
DATA_ARWN = "arwn"
TOPIC = "arwn/#"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ARWN platform."""

    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return

    @callback
    def async_sensor_event_received(msg: mqtt.ReceiveMessage) -> None:
        """Process MQTT events as sensors."""
        event = json_loads_object(msg.payload)

        try:
            device = parse_message(msg.topic, event)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Failed to parse ARWN message on topic %s", msg.topic)
            return

        if device is None:
            return

        if (store := hass.data.get(DATA_ARWN)) is None:
            store = hass.data[DATA_ARWN] = {}

        if "timestamp" in event:
            del event["timestamp"]

        for reading in device.readings:
            if not reading.expose:
                continue

            unique_id = (
                f"{msg.topic}/{reading.sensor_key}"
                if len(device.readings) > 1
                else msg.topic
            )

            try:
                device_class = (
                    SensorDeviceClass(reading.device_class)
                    if reading.device_class
                    else None
                )
                state_class = (
                    SensorStateClass(reading.state_class)
                    if reading.state_class
                    else None
                )
            except ValueError:
                _LOGGER.debug(
                    "Unknown device_class=%s or state_class=%s for sensor %s",
                    reading.device_class,
                    reading.state_class,
                    reading.sensor_name,
                )
                device_class = None
                state_class = None

            if unique_id not in store:
                sensor = ArwnSensor(
                    unique_id=unique_id,
                    name=reading.sensor_name,
                    state_key=reading.sensor_key,
                    units=reading.unit,
                    icon=reading.icon,
                    device_class=device_class,
                    state_class=state_class,
                    event=event,
                )
                store[unique_id] = sensor
                _LOGGER.debug(
                    "Registering sensor %(name)s => %(event)s",
                    {"name": reading.sensor_name, "event": event},
                )
                async_add_entities((sensor,), True)
            else:
                _LOGGER.debug(
                    "Recording sensor %(name)s => %(event)s",
                    {"name": reading.sensor_name, "event": event},
                )
                store[unique_id].set_event(event)

    await mqtt.async_subscribe(hass, TOPIC, async_sensor_event_received, 0)


class ArwnSensor(SensorEntity):
    """Representation of an ARWN sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        state_key: str,
        units: str,
        icon: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        event: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the sensor."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._state_key = state_key
        self._attr_native_unit_of_measurement = units
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        if event is not None:
            self._attr_extra_state_attributes = dict(event)
            self._attr_native_value = event.get(state_key)

    def set_event(self, event: dict[str, Any]) -> None:
        """Update the sensor with the most recent event."""
        self._attr_extra_state_attributes = dict(event)
        self._attr_native_value = event.get(self._state_key)
        self.async_write_ha_state()
