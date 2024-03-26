"""Support for the Netatmo sensors."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_URL_SECURITY,
    DOMAIN,
    EVENT_TYPE_DOOR_TAG_BIG_MOVE,
    EVENT_TYPE_DOOR_TAG_OPEN,
    EVENT_TYPE_DOOR_TAG_SMALL_MOVE,
    EVENT_TYPE_HOME_ALARM,
    EVENT_TYPE_TAG_UNINSTALLED,
    NETATMO_CREATE_OPENING_BINARY_SENSOR,
    NETATMO_CREATE_SIREN_BINARY_SENSOR,
    SIGNAL_NAME,
)
from .data_handler import HOME, NetatmoDevice
from .entity import NetatmoBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class NetatmoRequiredBinaryKeysMixin:
    """Mixin for required keys."""

    netatmo_name: str


@dataclass(frozen=True)
class NetatmoBinarySensorEntityDescription(
    BinarySensorEntityDescription, NetatmoRequiredBinaryKeysMixin
):
    """Describes Netatmo binary sensor entity."""


BINARY_SENSOR_SIREN_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="sounding",
        name="Sounding",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.SOUND,
        icon="mdi:home-sound-int",
    ),
    NetatmoBinarySensorEntityDescription(
        key="monitoring",
        name="Monitoring",
        netatmo_name="monitoring",
        device_class=BinarySensorDeviceClass.SAFETY,
        icon="mdi:alarm-light",
    ),
)

BINARY_SENSOR_SIREN_TYPES_KEYS = [desc.key for desc in BINARY_SENSOR_SIREN_TYPES]

BINARY_SENSOR_OPENING_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="opening",
        name="Opening",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:window-closed-variant",
    ),
    NetatmoBinarySensorEntityDescription(
        key="motion",
        name="Motion",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.MOTION,
        icon="mdi:motion-sensor",
    ),
    NetatmoBinarySensorEntityDescription(
        key="vibration",
        name="Vibration",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.VIBRATION,
        icon="mdi:vibrate",
    ),
)

BINARY_SENSOR_OPENING_TYPES_KEYS = [desc.key for desc in BINARY_SENSOR_OPENING_TYPES]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netatmo sensor platform."""

    @callback
    def netatmo_create_siren_binary_sensor(netatmo_device: NetatmoDevice) -> None:
        async_add_entities(
            NetatmoSirenBinarySensor(netatmo_device, description)
            for description in BINARY_SENSOR_SIREN_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_SIREN_BINARY_SENSOR, netatmo_create_siren_binary_sensor
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
            hass,
            NETATMO_CREATE_OPENING_BINARY_SENSOR,
            _create_opening_binary_sensor_entity,
        )
    )


class NetatmoSirenBinarySensor(NetatmoBaseEntity, BinarySensorEntity):
    """Implementation of a Netatmo weather/home coach sensor."""

    _attr_has_entity_name = True
    entity_description: NetatmoBinarySensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device.data_handler)
        self.entity_description = description

        self._module = netatmo_device.device
        self._id = self._module.entity_id
        self._bridge = self._module.bridge if self._module.bridge is not None else None
        self._device_name = self._module.name
        self._signal_name = netatmo_device.signal_name
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

        self._attr_name = f"{description.name}"
        self._model = self._module.device_type
        self._config_url = CONF_URL_SECURITY
        self._attr_unique_id = f"{self._id}-{description.key}"

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self._module.reachable:
            if self.available:
                self._attr_available = False
            return

        if (
            state := getattr(self._module, self.entity_description.netatmo_name)
        ) is None:
            return

        if self.entity_description.key == "sounding":
            self._attr_available = True
            if state in ("no_sound", "now_news", "warning"):
                self.is_on = False
            else:
                self.is_on = True
        elif self.entity_description.key == "monitoring":
            self._attr_available = True
            self.is_on = not state
        else:
            self._attr_available = False

        self.async_write_ha_state()

    @callback
    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        if self.entity_description.key == "sounding":
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"signal-{DOMAIN}-webhook-{EVENT_TYPE_HOME_ALARM}",
                    self.handle_event,
                )
            )

    @callback
    async def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        _LOGGER.debug(
            "receive event %s on  %s and %s",
            event["type"],
            self._device_name,
            self.entity_description.key,
        )
        if event["type"] == EVENT_TYPE_HOME_ALARM:
            if event["data"]["device_id"] == self._bridge:
                _LOGGER.debug(
                    "handle_event %s on  %s and %s",
                    EVENT_TYPE_HOME_ALARM,
                    self._device_name,
                    self.entity_description.key,
                )
                self.data_handler.async_force_update(self._signal_name)
        else:
            _LOGGER.debug(
                "handle_event %s on  %s and %s not supported",
                event["type"],
                self._device_name,
                self.entity_description.key,
            )


class NetatmoOpeningBinarySensor(NetatmoBaseEntity, BinarySensorEntity):
    """Implementation of a Netatmo weather/home coach sensor."""

    _attr_has_entity_name = True
    entity_description: NetatmoBinarySensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device.data_handler)
        self.entity_description = description

        self._module = netatmo_device.device
        self._id = self._module.entity_id
        self._bridge = self._module.bridge if self._module.bridge is not None else None
        self._device_name = self._module.name
        self._signal_name = netatmo_device.signal_name
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

        self._attr_name = f"{description.name}"
        self._model = self._module.device_type
        self._config_url = CONF_URL_SECURITY
        self._attr_unique_id = f"{self._id}-{description.key}"
        self._hasEvent = False

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self._module.reachable:
            if self.available:
                self._attr_available = False
            return

        if (
            state := getattr(self._module, self.entity_description.netatmo_name)
        ) is None:
            return

        if self.entity_description.key == "opening":
            self._attr_available = True
            if state == "open":
                self.is_on = True
            elif state == "closed":
                self.is_on = False
            else:
                self._attr_available = False
                self.is_on = None
        elif self.entity_description.key == "motion":
            self._attr_available = True
            self.is_on = False
        elif self.entity_description.key == "vibration":
            self._attr_available = True
            self.is_on = False
        else:
            self._attr_available = False
            self.is_on = None

        self.async_write_ha_state()

    @callback
    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        for event_type in (
            EVENT_TYPE_DOOR_TAG_OPEN,
            EVENT_TYPE_TAG_UNINSTALLED,
        ):
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"signal-{DOMAIN}-webhook-{event_type}",
                    self.handle_event,
                )
            )
        if self.entity_description.key in ("motion", "vibration"):
            for event_type in (
                EVENT_TYPE_DOOR_TAG_BIG_MOVE,
                EVENT_TYPE_DOOR_TAG_SMALL_MOVE,
            ):
                self.async_on_remove(
                    async_dispatcher_connect(
                        self.hass,
                        f"signal-{DOMAIN}-webhook-{event_type}",
                        self.handle_event,
                    )
                )

    @callback
    async def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        _LOGGER.debug(
            "receive event %s on  %s and %s",
            event["type"],
            self._device_name,
            self.entity_description.key,
        )
        if event["type"] == EVENT_TYPE_DOOR_TAG_OPEN:
            if event["data"]["module_id"] == self._id:
                _LOGGER.debug(
                    "handle_event %s on  %s and %s",
                    EVENT_TYPE_DOOR_TAG_OPEN,
                    self._device_name,
                    self.entity_description.key,
                )
                state = True
                if self.entity_description.key in ("motion", "vibration"):
                    state = False
                self.is_on = state
                self._attr_available = True
                self.async_write_ha_state()
        elif event["type"] == EVENT_TYPE_DOOR_TAG_BIG_MOVE:
            if event["data"]["module_id"] == self._id:
                _LOGGER.debug(
                    "handle_event %s on  %s and %s",
                    event["type"],
                    self._device_name,
                    self.entity_description.key,
                )
                state = True
                if self.entity_description.key == "vibration":
                    state = False
                self.is_on = state
                self._attr_available = True
                self.async_write_ha_state()
        elif event["type"] == EVENT_TYPE_DOOR_TAG_SMALL_MOVE:
            if event["data"]["module_id"] == self._id:
                _LOGGER.debug(
                    "handle_event %s on  %s and %s",
                    event["type"],
                    self._device_name,
                    self.entity_description.key,
                )
                state = True
                if self.entity_description.key == "motion":
                    state = False
                self.is_on = state
                self._attr_available = True
                self.async_write_ha_state()
        elif event["type"] == EVENT_TYPE_TAG_UNINSTALLED:
            if event["data"]["module_id"] == self._id:
                _LOGGER.debug(
                    "handle_event %s on  %s and %s",
                    EVENT_TYPE_DOOR_TAG_OPEN,
                    self._device_name,
                    self.entity_description.key,
                )
                self.is_on = None
                self._attr_available = False
                self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "handle_event %s on  %s and %s not supported",
                event["type"],
                self._device_name,
                self.entity_description.key,
            )


def process_rf(strength: int) -> str:
    """Process wifi signal strength and return string for display."""
    if strength >= 90:
        return "Low"
    if strength >= 76:
        return "Medium"
    if strength >= 60:
        return "High"
    return "Full"


def process_wifi(strength: int) -> str:
    """Process wifi signal strength and return string for display."""
    if strength >= 86:
        return "Low"
    if strength >= 71:
        return "Medium"
    if strength >= 56:
        return "High"
    return "Full"
