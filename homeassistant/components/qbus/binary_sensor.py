"""Support for Qbus binary sensor."""

from dataclasses import dataclass
from typing import cast

from qbusmqttapi.discovery import QbusMqttDevice, QbusMqttOutput
from qbusmqttapi.state import QbusMqttDeviceState, QbusMqttWeatherState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import QbusConfigEntry
from .entity import QbusEntity, create_device_identifier, determine_new_outputs

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class QbusWeatherDescription(BinarySensorEntityDescription):
    """Description for Qbus weather entities."""

    property: str


_WEATHER_DESCRIPTIONS = (
    QbusWeatherDescription(
        key="raining",
        property="raining",
        translation_key="raining",
    ),
    QbusWeatherDescription(
        key="twilight",
        property="twilight",
        translation_key="twilight",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""

    coordinator = entry.runtime_data
    added_outputs: list[QbusMqttOutput] = []
    added_controllers: list[str] = []

    def _create_weather_entities() -> list[BinarySensorEntity]:
        new_outputs = determine_new_outputs(
            coordinator, added_outputs, lambda output: output.type == "weatherstation"
        )

        return [
            QbusWeatherBinarySensor(output, description)
            for output in new_outputs
            for description in _WEATHER_DESCRIPTIONS
        ]

    def _create_controller_entities() -> list[BinarySensorEntity]:
        if coordinator.data and coordinator.data.id not in added_controllers:
            added_controllers.extend(coordinator.data.id)
            return [QbusControllerConnectedBinarySensor(coordinator.data)]

        return []

    def _check_outputs() -> None:
        entities = [*_create_weather_entities(), *_create_controller_entities()]
        async_add_entities(entities)

    _check_outputs()
    entry.async_on_unload(coordinator.async_add_listener(_check_outputs))


class QbusWeatherBinarySensor(QbusEntity, BinarySensorEntity):
    """Representation of a Qbus weather binary sensor."""

    _state_cls = QbusMqttWeatherState

    entity_description: QbusWeatherDescription

    def __init__(
        self, mqtt_output: QbusMqttOutput, description: QbusWeatherDescription
    ) -> None:
        """Initialize binary sensor entity."""

        super().__init__(mqtt_output, id_suffix=description.key)

        self.entity_description = description

    async def _handle_state_received(self, state: QbusMqttWeatherState) -> None:
        if value := state.read_property(self.entity_description.property, None):
            self._attr_is_on = (
                None if value is None else cast(str, value).lower() == "true"
            )


class QbusControllerConnectedBinarySensor(BinarySensorEntity):
    """Representation of the Qbus controller connected sensor."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(self, controller: QbusMqttDevice) -> None:
        """Initialize binary sensor entity."""
        self._controller = controller

        self._attr_unique_id = f"ctd_{controller.serial_number}_connected"
        self._attr_device_info = DeviceInfo(
            identifiers={create_device_identifier(controller)}
        )
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"qbus_controller_{self._controller.id}_state",
                self._state_received,
            )
        )

    @callback
    def _state_received(self, state: QbusMqttDeviceState) -> None:
        self._attr_is_on = state.properties.connected if state.properties else None
        self.async_schedule_update_ha_state()
