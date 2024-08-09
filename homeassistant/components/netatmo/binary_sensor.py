"""Support for Netatmo binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_URL_SECURITY,
    DOMAIN,
    EVENT_TYPE_DOOR_TAG_BIG_MOVE,
    EVENT_TYPE_DOOR_TAG_OPEN,
    EVENT_TYPE_DOOR_TAG_SMALL_MOVE,
    EVENT_TYPE_HOME_ALARM,
    NETATMO_CREATE_OPENING_SENSOR,
    NETATMO_CREATE_SIREN_SENSOR,
    NETATMO_CREATE_WEATHER_SENSOR,
)
from .data_handler import HOME, SIGNAL_NAME, NetatmoDevice
from .entity import NetatmoModuleEntity, NetatmoWeatherModuleEntity


def process_open_status(status: StateType) -> bool | None:
    """Process health index and return string for display."""
    if not isinstance(status, str):
        return None

    if status == "open":
        return True

    return False


def process_monitoring_status(status: StateType) -> bool | None:
    """Process monitoring siren status and return boolean for display."""
    if not isinstance(status, bool):
        return None

    return not status


def process_sound_status(status: StateType) -> bool | None:
    """Process sound siren status and return boolean for display."""
    if not isinstance(status, str):
        return None

    if status == "sound":
        return True

    return False


@dataclass(frozen=True, kw_only=True)
class NetatmoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Netatmo sensor entity."""

    netatmo_name: str
    value_fn: Callable[[StateType], StateType] = lambda x: x


BINARY_SENSOR_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="reachable",
        netatmo_name="reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


BINARY_SENSOR_OPENING_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="opening",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=process_open_status,
    ),
    NetatmoBinarySensorEntityDescription(
        key="reachable",
        netatmo_name="reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    NetatmoBinarySensorEntityDescription(
        key="motion",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.MOTION,
        value_fn=lambda x: False,
    ),
    NetatmoBinarySensorEntityDescription(
        key="vibration",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.VIBRATION,
        value_fn=lambda x: False,
    ),
)

OPENING_KEYS_TO_EVENT = {
    "motion": EVENT_TYPE_DOOR_TAG_BIG_MOVE,
    "opening": EVENT_TYPE_DOOR_TAG_OPEN,
    "vibration": EVENT_TYPE_DOOR_TAG_SMALL_MOVE,
}

BINARY_SENSOR_SIREN_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="monitoring",
        netatmo_name="monitoring",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=process_monitoring_status,
    ),
    NetatmoBinarySensorEntityDescription(
        key="sound",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.SOUND,
        value_fn=process_sound_status,
    ),
    NetatmoBinarySensorEntityDescription(
        key="reachable",
        netatmo_name="reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Netatmo binary sensors based on a config entry."""

    @callback
    def _create_weather_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        async_add_entities(
            NetatmoWeatherBinarySensor(netatmo_device, description)
            for description in BINARY_SENSOR_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_WEATHER_SENSOR, _create_weather_binary_sensor_entity
        )
    )

    @callback
    def _create_opening_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        async_add_entities(
            NetatmoOpeningBinarySensor(netatmo_device, description)
            for description in BINARY_SENSOR_OPENING_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_OPENING_SENSOR, _create_opening_binary_sensor_entity
        )
    )

    @callback
    def _create_siren_binary_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        async_add_entities(
            NetatmoSirenBinarySensor(netatmo_device, description)
            for description in BINARY_SENSOR_SIREN_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_SIREN_SENSOR, _create_siren_binary_sensor_entity
        )
    )


class NetatmoWeatherBinarySensor(NetatmoWeatherModuleEntity, BinarySensorEntity):
    """Implementation of a Netatmo binary sensor."""

    def __init__(
        self, device: NetatmoDevice, description: NetatmoBinarySensorEntityDescription
    ) -> None:
        """Initialize a Netatmo binary sensor."""
        super().__init__(device)
        self.entity_description = description
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._attr_is_on = self.device.reachable
        self.async_write_ha_state()


class NetatmoOpeningSirenBinarySensor(NetatmoModuleEntity, BinarySensorEntity):
    """Implementation of a Netatmo binary sensor."""

    entity_description: NetatmoBinarySensorEntityDescription
    _attr_configuration_url = CONF_URL_SECURITY

    def __init__(
        self, device: NetatmoDevice, description: NetatmoBinarySensorEntityDescription
    ) -> None:
        """Initialize a Netatmo binary sensor."""
        super().__init__(device)
        self.entity_description = description
        self._attr_unique_id = f"{self.device.entity_id}-{description.key}"
        self._attr_translation_key = description.netatmo_name

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: f"{HOME}-{self.home.entity_id}",
                },
            ]
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self.device.reachable:
            if self.available:
                self._attr_available = False
            return

        state = cast(
            StateType, getattr(self.device, self.entity_description.netatmo_name)
        )
        if state is None:
            self._attr_is_on = None
        else:
            self._attr_is_on = bool(self.entity_description.value_fn(state))

        self._attr_available = True
        self.async_write_ha_state()


class NetatmoOpeningBinarySensor(NetatmoOpeningSirenBinarySensor):
    """Implementation of a Netatmo binary sensor."""

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        for key in OPENING_KEYS_TO_EVENT.items():
            if key[0] == self.entity_description.key:
                self.async_on_remove(
                    async_dispatcher_connect(
                        self.hass,
                        f"signal-{DOMAIN}-webhook-{key[1]}",
                        self.handle_event,
                    )
                )

    @callback
    def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        data = event["data"]

        if (
            data["home_id"] == self.home.entity_id
            and data["module_id"] == self.device.entity_id
        ):
            self.is_on = True
            self.async_write_ha_state()


class NetatmoSirenBinarySensor(NetatmoOpeningSirenBinarySensor):
    """Implementation of a Netatmo binary sensor."""

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        if self.entity_description.key == "monitoring":
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"signal-{DOMAIN}-webhook-{EVENT_TYPE_HOME_ALARM}",
                    self.handle_event,
                )
            )

    @callback
    def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        data = event["data"]

        if (
            self.home.entity_id == data["home_id"]
            and self.device.bridge == data["device_id"]
        ):
            self.data_handler.async_force_update(f"{HOME}-{self.home.entity_id}")
