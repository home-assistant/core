"""Support for MQTT sensors."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
import logging

from pyliblorawan.models import Uplink
from pyliblorawan.network_servers.helpers import normalize_unknown_uplink

from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import devices
from .const import DOMAIN, MANUFACTURER, TTN_TOPIC

_LOGGER = logging.getLogger(__name__)


@dataclass
class BrowanSensorDescriptionMixin:
    """Mixin for Browan sensor."""


@dataclass
class BrowanSensorEntityDescription(
    SensorEntityDescription, BrowanSensorDescriptionMixin
):
    """Class describing Browan sensor entities."""

    name: str | None = None


ENTITY_DESCRIPTIONS: tuple[BrowanSensorEntityDescription, ...] = (
    BrowanSensorEntityDescription(
        key=ATTR_BATTERY_LEVEL,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        translation_key="battery_level",
    ),
    BrowanSensorEntityDescription(
        key=ATTR_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="temperature",
    ),
)


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
    """Set up Browan sensor."""
    entities = []

    # Device should not generate any error as it is returned by
    # the config flow selector, but catch the error in case something
    # goes wrong somewhere
    if not config_entry.data["model"].isalnum():
        _LOGGER.error(
            'Device name "%s" from %s is invalid',
            config_entry.data["model"],
            MANUFACTURER.capitalize(),
        )
        return
    try:
        device = getattr(devices, f'Hass{config_entry.data["model"]}')
    except AttributeError:
        _LOGGER.error(
            'Device "%s" from %s is unknown',
            config_entry.data["model"],
            MANUFACTURER.capitalize(),
        )
        return

    coordinator = LorawanSensorCoordinator(hass, config_entry, device.parse_uplink)
    for key in device.supported_sensors():
        description = [
            description for description in ENTITY_DESCRIPTIONS if key == description.key
        ][0]
        entities.append(
            LorawanSensorEntity(hass, config_entry, coordinator, description)
        )
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
        uplink = normalize_unknown_uplink(uplink)
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
        description: BrowanSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description: BrowanSensorEntityDescription = description

        self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"
        self._config = config_entry
        self._hass = hass
        self._sensor_data_key = description.key
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
        # if self.name is None:
        #    raise ValueError("name should not be None")
        # if isinstance(self.name, UndefinedType):
        #    raise TypeError("name should not be undefined")
        return DeviceInfo(
            identifiers={(DOMAIN, self._config.unique_id)},
            name=self._config.title,
            manufacturer=MANUFACTURER,
            model=self._config.data["model"],
        )
