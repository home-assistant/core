"""Platform for NASweb sensors."""

from __future__ import annotations

import logging
import time

from webio_api import Input as NASwebInput, TempSensor

from homeassistant.components.sensor import (
    DOMAIN as DOMAIN_SENSOR,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    BaseCoordinatorEntity,
    BaseDataUpdateCoordinatorProtocol,
)

from . import NASwebConfigEntry
from .const import DOMAIN, KEY_TEMP_SENSOR, STATUS_UPDATE_MAX_TIME_INTERVAL

SENSOR_INPUT_TRANSLATION_KEY = "sensor_input"
STATE_UNDEFINED = "undefined"
STATE_TAMPER = "tamper"
STATE_ACTIVE = "active"
STATE_NORMAL = "normal"
STATE_PROBLEM = "problem"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: NASwebConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Sensor platform."""
    coordinator = config.runtime_data
    current_inputs: set[int] = set()

    @callback
    def _check_entities() -> None:
        received_inputs: dict[int, NASwebInput] = {
            entry.index: entry for entry in coordinator.webio_api.inputs
        }
        added = {i for i in received_inputs if i not in current_inputs}
        removed = {i for i in current_inputs if i not in received_inputs}
        entities_to_add: list[InputStateSensor] = []
        for index in added:
            webio_input = received_inputs[index]
            if not isinstance(webio_input, NASwebInput):
                _LOGGER.error("Cannot create InputStateSensor without NASwebInput")
                continue
            new_input = InputStateSensor(coordinator, webio_input)
            entities_to_add.append(new_input)
            current_inputs.add(index)
        async_add_entities(entities_to_add)
        entity_registry = er.async_get(hass)
        for index in removed:
            unique_id = f"{DOMAIN}.{config.unique_id}.input.{index}"
            if entity_id := entity_registry.async_get_entity_id(
                DOMAIN_SENSOR, DOMAIN, unique_id
            ):
                entity_registry.async_remove(entity_id)
                current_inputs.remove(index)
            else:
                _LOGGER.warning("Failed to remove old input: no entity_id")

    coordinator.async_add_listener(_check_entities)
    _check_entities()

    nasweb_temp_sensor = coordinator.data[KEY_TEMP_SENSOR]
    temp_sensor = TemperatureSensor(coordinator, nasweb_temp_sensor)
    async_add_entities([temp_sensor])


class BaseSensorEntity(SensorEntity, BaseCoordinatorEntity):
    """Base class providing common functionality."""

    def __init__(self, coordinator: BaseDataUpdateCoordinatorProtocol) -> None:
        """Initialize base sensor."""
        super().__init__(coordinator)
        self._attr_available = False
        self._attr_has_entity_name = True
        self._attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    def _set_attr_available(
        self, entity_last_update: float, available: bool | None
    ) -> None:
        if (
            self.coordinator.last_update is None
            or time.time() - entity_last_update >= STATUS_UPDATE_MAX_TIME_INTERVAL
        ):
            self._attr_available = False
        else:
            self._attr_available = available if available is not None else False

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        Scheduling updates is not necessary, the coordinator takes care of updates via push notifications.
        """


class InputStateSensor(BaseSensorEntity):
    """Entity representing NASweb input."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: list[str] = [
        STATE_UNDEFINED,
        STATE_TAMPER,
        STATE_ACTIVE,
        STATE_NORMAL,
        STATE_PROBLEM,
    ]
    _attr_translation_key = SENSOR_INPUT_TRANSLATION_KEY

    def __init__(
        self,
        coordinator: BaseDataUpdateCoordinatorProtocol,
        nasweb_input: NASwebInput,
    ) -> None:
        """Initialize InputStateSensor entity."""
        super().__init__(coordinator)
        self._input = nasweb_input
        self._attr_native_value: str | None = None
        self._attr_translation_placeholders = {"index": f"{nasweb_input.index:2d}"}
        self._attr_unique_id = (
            f"{DOMAIN}.{self._input.webio_serial}.input.{self._input.index}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._input.webio_serial)},
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._input.state is None or self._input.state in self._attr_options:
            self._attr_native_value = self._input.state
        else:
            _LOGGER.warning("Received unrecognized input state: %s", self._input.state)
            self._attr_native_value = None
        self._set_attr_available(self._input.last_update, self._input.available)
        self.async_write_ha_state()


class TemperatureSensor(BaseSensorEntity):
    """Entity representing NASweb temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: BaseDataUpdateCoordinatorProtocol,
        nasweb_temp_sensor: TempSensor,
    ) -> None:
        """Initialize TemperatureSensor entity."""
        super().__init__(coordinator)
        self._temp_sensor = nasweb_temp_sensor
        self._attr_unique_id = f"{DOMAIN}.{self._temp_sensor.webio_serial}.temp_sensor"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._temp_sensor.webio_serial)}
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._temp_sensor.value
        self._set_attr_available(
            self._temp_sensor.last_update, self._temp_sensor.available
        )
        self.async_write_ha_state()
