"""Support for MQTT sensors."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import importlib
import json
import logging

from pyliblorawan.models import Uplink
from pyliblorawan.network_servers.ttn import TTN

from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UndefinedType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, TTN_TOPIC
from .models import SensorTypes

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT sensor through YAML and through MQTT discovery."""

    await _async_setup_entity(hass, async_add_entities, config_entry)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config_entry: ConfigEntry,
) -> None:
    """Set up LoRaWAN sensor."""
    entities = []

    # Device/manufacture should not generate any error as they are returned
    # by the config flow selector, but catch the error in case something
    # goes wrong somewhere
    if not config_entry.data["manufacturer"].isalnum():
        _LOGGER.error(
            'Manufacturer name "%s" is invalid', config_entry.data["manufacturer"]
        )
        return
    try:
        manufacturer = importlib.import_module(
            f'homeassistant.components.lorawan.devices.{config_entry.data["manufacturer"]}',
        )
    except ImportError:
        _LOGGER.error('Manufacturer "%s" is unknown', config_entry.data["manufacturer"])
        return

    if not config_entry.data["model"].isalnum():
        _LOGGER.error(
            'Device name "%s" from %s is invalid',
            config_entry.data["model"],
            config_entry.data["manufacturer"].capitalize(),
        )
        return
    try:
        device = getattr(manufacturer, f'Hass{config_entry.data["model"]}')
    except AttributeError:
        _LOGGER.error(
            'Device "%s" from %s is unknown',
            config_entry.data["model"],
            config_entry.data["manufacturer"].capitalize(),
        )
        return

    coordinator = LorawanSensorCoordinator(hass, config_entry, device.parse_uplink)
    for sensor in device.supported_sensors():
        entities.append(LorawanSensorEntity(hass, config_entry, coordinator, sensor))
    async_add_entities(entities)
    await coordinator.subscribe()


class LorawanSensorCoordinator(DataUpdateCoordinator):
    """Allows to update all entities with one payload reception."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        uplink_parser: Callable[[Uplink], Awaitable[Uplink]],
    ) -> None:
        """Initialize the coordinator."""
        self._config = config_entry
        self._uplink_parser = uplink_parser
        super().__init__(
            hass,
            _LOGGER,
            name=f"LorawanSensorCoordinator.{config_entry.title}",
        )

    async def _message_received(self, msg: ReceiveMessage) -> None:
        """Handle uplink, parse and normalize it."""
        uplink = json.loads(msg.payload)
        uplink = TTN.normalize_uplink(uplink)
        await self._uplink_parser(uplink)

        self.async_set_updated_data(uplink)

    async def subscribe(self) -> None:
        """Subscribe to MQTT messages and handle them."""
        topic = TTN_TOPIC.replace("<DEVICE_ID>", self._config.title)
        await self.hass.components.mqtt.async_subscribe(topic, self._message_received)


class LorawanSensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of a sensor entity that can be updated using LoRaWAN."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        coordinator: LorawanSensorCoordinator,
        sensor: SensorTypes.SensorType,
    ) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = f"{config_entry.unique_id}_{sensor.NAME}"
        self._attr_device_class = sensor.DEVICE_CLASS
        self._attr_name = sensor.NAME
        self._attr_native_unit_of_measurement = sensor.UNIT

        self._config = config_entry
        self._hass = hass
        self._sensor_data_key = sensor.DATA_KEY
        super().__init__(coordinator)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        uplink: Uplink = self.coordinator.data
        self._attr_native_value = getattr(uplink.sensors, self._sensor_data_key)
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        if self._config.unique_id is None:
            raise ValueError("config.unique_id should not be None")
        if self.name is None:
            raise ValueError("name should not be None")
        if isinstance(self.name, UndefinedType):
            raise TypeError("name should not be undefined")
        return DeviceInfo(
            identifiers={(DOMAIN, self._config.unique_id)},
            name=self._config.title,
            manufacturer=self._config.data["manufacturer"],
            model=self._config.data["model"],
        )
