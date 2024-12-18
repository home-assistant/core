"""Platform for NASweb sensors."""

from __future__ import annotations

import logging
import time

from webio_api import Input as NASwebInput, TempSensor
from webio_api.const import KEY_TEMP_SENSOR

from homeassistant.components.sensor import (
    DOMAIN as DOMAIN_SENSOR,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    BaseCoordinatorEntity,
    BaseDataUpdateCoordinatorProtocol,
)

from . import NASwebConfigEntry
from .const import (
    DOMAIN,
    STATE_FAULT,
    STATE_TAMPER,
    STATE_UNDEFINED,
    STATE_VIGIL,
    STATE_VIOLATION,
    STATUS_UPDATE_MAX_TIME_INTERVAL,
)
from .coordinator import NASwebCoordinator

SENSOR_INPUT_TRANSLATION_KEY = "sensor_input"

_LOGGER = logging.getLogger(__name__)


def _get_input(coordinator: NASwebCoordinator, index: int) -> NASwebInput | None:
    for entry in coordinator.webio_api.inputs:
        if entry.index == index:
            return entry
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config: NASwebConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Sensor platform."""
    coordinator = config.runtime_data
    current_inputs: set[int] = set()

    @callback
    def _check_entities() -> None:
        received_inputs = {entry.index for entry in coordinator.webio_api.inputs}
        added = {i for i in received_inputs if i not in current_inputs}
        removed = {i for i in current_inputs if i not in received_inputs}
        entities_to_add: list[InputStateSensor] = []
        for index in added:
            webio_input = _get_input(coordinator, index)
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


class InputStateSensor(SensorEntity, BaseCoordinatorEntity):
    """Entity representing NASweb input."""

    def __init__(
        self,
        coordinator: BaseDataUpdateCoordinatorProtocol,
        nasweb_input: NASwebInput,
    ) -> None:
        """Initialize zone entity."""
        super().__init__(coordinator)
        self._input = nasweb_input
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options: list[str] = [
            STATE_FAULT,
            STATE_TAMPER,
            STATE_UNDEFINED,
            STATE_VIGIL,
            STATE_VIOLATION,
        ]
        self._attr_native_value: str | None = None
        self._attr_available = False
        self._attr_icon = "mdi:import"
        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self._attr_translation_key = SENSOR_INPUT_TRANSLATION_KEY
        self._attr_translation_placeholders = {"index": f"{nasweb_input.index:2d}"}
        self._attr_unique_id = (
            f"{DOMAIN}.{self._input.webio_serial}.input.{self._input.index}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._input.webio_serial)},
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._input.state is None or self._input.state in self._attr_options:
            self._attr_native_value = self._input.state
        else:
            _LOGGER.warning("Received unrecognized input state: %s", self._input.state)
            self._attr_native_value = None
        if (
            self.coordinator.last_update is None
            or time.time() - self._input.last_update >= STATUS_UPDATE_MAX_TIME_INTERVAL
        ):
            self._attr_available = False
        else:
            self._attr_available = (
                self._input.available if self._input.available is not None else False
            )
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        Scheduling updates is not necessary, the coordinator takes care of updates via push notifications.
        """


class TemperatureSensor(SensorEntity, BaseCoordinatorEntity):
    """Entity representing NASweb temperature sensor."""

    def __init__(
        self,
        coordinator: BaseDataUpdateCoordinatorProtocol,
        nasweb_temp_sensor: TempSensor,
    ) -> None:
        """Initialize TemperatureSensor."""
        super().__init__(coordinator)
        self._temp_sensor = nasweb_temp_sensor
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_available = False
        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self._attr_unique_id = f"{DOMAIN}.{self._temp_sensor.webio_serial}.temp_sensor"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._temp_sensor.webio_serial)}
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self._temp_sensor.value
        if (
            self.coordinator.last_update is None
            or time.time() - self._temp_sensor.last_update
            >= STATUS_UPDATE_MAX_TIME_INTERVAL
        ):
            self._attr_available = False
        else:
            self._attr_available = (
                self._temp_sensor.available
                if self._temp_sensor.available is not None
                else False
            )
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        Scheduling updates is not necessary, the coordinator takes care of updates via push notifications.
        """
