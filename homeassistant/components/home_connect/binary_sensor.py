"""Provides a binary sensor for Home Connect."""

from dataclasses import dataclass, field
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HomeConnectDevice
from .const import (
    ATTR_DEVICE,
    ATTR_VALUE,
    BSH_DOOR_STATE,
    BSH_DOOR_STATE_CLOSED,
    BSH_DOOR_STATE_LOCKED,
    BSH_DOOR_STATE_OPEN,
    BSH_REMOTE_CONTROL_ACTIVATION_STATE,
    BSH_REMOTE_START_ALLOWANCE_STATE,
    DOMAIN,
    REFRIGERATION_STATUS_DOOR_CHILLER,
    REFRIGERATION_STATUS_DOOR_CLOSED,
    REFRIGERATION_STATUS_DOOR_FREEZER,
    REFRIGERATION_STATUS_DOOR_OPEN,
    REFRIGERATION_STATUS_DOOR_REFRIGERATOR,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HomeConnectBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Entity Description class for binary sensors."""

    state_key: str | None
    device_class: BinarySensorDeviceClass | None = BinarySensorDeviceClass.DOOR
    boolean_map: dict[str, bool] = field(
        default_factory=lambda: {
            REFRIGERATION_STATUS_DOOR_CLOSED: False,
            REFRIGERATION_STATUS_DOOR_OPEN: True,
        }
    )


BINARY_SENSORS: tuple[HomeConnectBinarySensorEntityDescription, ...] = (
    HomeConnectBinarySensorEntityDescription(
        key="Chiller Door",
        state_key=REFRIGERATION_STATUS_DOOR_CHILLER,
    ),
    HomeConnectBinarySensorEntityDescription(
        key="Freezer Door",
        state_key=REFRIGERATION_STATUS_DOOR_FREEZER,
    ),
    HomeConnectBinarySensorEntityDescription(
        key="Refrigerator Door",
        state_key=REFRIGERATION_STATUS_DOOR_REFRIGERATOR,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect binary sensor."""

    def get_entities() -> list[BinarySensorEntity]:
        entities: list[BinarySensorEntity] = []
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get(CONF_ENTITIES, {}).get("binary_sensor", [])
            entities += [HomeConnectBinarySensor(**d) for d in entity_dicts]
            device: HomeConnectDevice = device_dict[ATTR_DEVICE]
            # Auto-discover entities
            entities.extend(
                HomeConnectFridgeDoorBinarySensor(
                    device=device, entity_description=description
                )
                for description in BINARY_SENSORS
                if description.state_key in device.appliance.status
            )
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectBinarySensor(HomeConnectEntity, BinarySensorEntity):
    """Binary sensor for Home Connect."""

    def __init__(
        self,
        device: HomeConnectDevice,
        desc: str,
        sensor_type: str,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(device, desc)
        self._attr_device_class = device_class
        self._type = sensor_type
        self._false_value_list = None
        self._true_value_list = None
        if self._type == "door":
            self._update_key = BSH_DOOR_STATE
            self._false_value_list = [BSH_DOOR_STATE_CLOSED, BSH_DOOR_STATE_LOCKED]
            self._true_value_list = [BSH_DOOR_STATE_OPEN]
        elif self._type == "remote_control":
            self._update_key = BSH_REMOTE_CONTROL_ACTIVATION_STATE
        elif self._type == "remote_start":
            self._update_key = BSH_REMOTE_START_ALLOWANCE_STATE

    @property
    def available(self) -> bool:
        """Return true if the binary sensor is available."""
        return self._attr_is_on is not None

    async def async_update(self) -> None:
        """Update the binary sensor's status."""
        state = self.device.appliance.status.get(self._update_key, {})
        if not state:
            self._attr_is_on = None
            return

        value = state.get(ATTR_VALUE)
        if self._false_value_list and self._true_value_list:
            if value in self._false_value_list:
                self._attr_is_on = False
            elif value in self._true_value_list:
                self._attr_is_on = True
            else:
                _LOGGER.warning(
                    "Unexpected value for HomeConnect %s state: %s", self._type, state
                )
                self._attr_is_on = None
        elif isinstance(value, bool):
            self._attr_is_on = value
        else:
            _LOGGER.warning(
                "Unexpected value for HomeConnect %s state: %s", self._type, state
            )
            self._attr_is_on = None
        _LOGGER.debug("Updated, new state: %s", self._attr_is_on)


class HomeConnectFridgeDoorBinarySensor(HomeConnectEntity, BinarySensorEntity):
    """Binary sensor for Home Connect Fridge Doors."""

    entity_description: HomeConnectBinarySensorEntityDescription

    def __init__(
        self,
        device: HomeConnectDevice,
        entity_description: HomeConnectBinarySensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = entity_description
        super().__init__(device, entity_description.key)

    async def async_update(self) -> None:
        """Update the binary sensor's status."""
        _LOGGER.debug(
            "Updating: %s, cur state: %s",
            self._attr_unique_id,
            self.state,
        )
        self._attr_is_on = self.entity_description.boolean_map.get(
            self.device.appliance.status.get(self.entity_description.state_key, {}).get(
                ATTR_VALUE
            )
        )
        self._attr_available = self._attr_is_on is not None
        _LOGGER.debug(
            "Updated: %s, new state: %s",
            self._attr_unique_id,
            self.state,
        )
