"""Support for a ScreenLogic Binary Sensor."""
from screenlogicpy.const import DATA as SL_DATA, DEVICE_TYPE, EQUIPMENT, ON_OFF

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ScreenlogicEntity
from .const import DOMAIN

SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS = {DEVICE_TYPE.ALARM: BinarySensorDeviceClass.PROBLEM}

SUPPORTED_CONFIG_BINARY_SENSORS = (
    "freeze_mode",
    "pool_delay",
    "spa_delay",
    "cleaner_delay",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    entities = []
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Generic binary sensor
    entities.append(ScreenLogicBinarySensor(coordinator, "chem_alarm"))

    entities.extend(
        [
            ScreenlogicConfigBinarySensor(coordinator, cfg_sensor)
            for cfg_sensor in coordinator.data[SL_DATA.KEY_CONFIG]
            if cfg_sensor in SUPPORTED_CONFIG_BINARY_SENSORS
        ]
    )

    if (
        coordinator.data[SL_DATA.KEY_CONFIG]["equipment_flags"]
        & EQUIPMENT.FLAG_INTELLICHEM
    ):
        # IntelliChem alarm sensors
        entities.extend(
            [
                ScreenlogicChemistryAlarmBinarySensor(coordinator, chem_alarm)
                for chem_alarm in coordinator.data[SL_DATA.KEY_CHEMISTRY][
                    SL_DATA.KEY_ALERTS
                ]
                if chem_alarm != "_raw"
            ]
        )

        # Intellichem notification sensors
        entities.extend(
            [
                ScreenlogicChemistryNotificationBinarySensor(coordinator, chem_notif)
                for chem_notif in coordinator.data[SL_DATA.KEY_CHEMISTRY][
                    SL_DATA.KEY_NOTIFICATIONS
                ]
                if chem_notif != "_raw"
            ]
        )

    if (
        coordinator.data[SL_DATA.KEY_CONFIG]["equipment_flags"]
        & EQUIPMENT.FLAG_CHLORINATOR
    ):
        # SCG binary sensor
        entities.append(ScreenlogicSCGBinarySensor(coordinator, "scg_status"))

    async_add_entities(entities)


class ScreenLogicBinarySensor(ScreenlogicEntity, BinarySensorEntity):
    """Representation of the basic ScreenLogic binary sensor entity."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        """Return the sensor name."""
        return self.sensor["name"]

    @property
    def device_class(self):
        """Return the device class."""
        device_type = self.sensor.get("device_type")
        return SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS.get(device_type)

    @property
    def is_on(self) -> bool:
        """Determine if the sensor is on."""
        return self.sensor["value"] == ON_OFF.ON

    @property
    def sensor(self):
        """Shortcut to access the sensor data."""
        return self.coordinator.data[SL_DATA.KEY_SENSORS][self._data_key]


class ScreenlogicChemistryAlarmBinarySensor(ScreenLogicBinarySensor):
    """Representation of a ScreenLogic IntelliChem alarm binary sensor entity."""

    @property
    def sensor(self):
        """Shortcut to access the sensor data."""
        return self.coordinator.data[SL_DATA.KEY_CHEMISTRY][SL_DATA.KEY_ALERTS][
            self._data_key
        ]


class ScreenlogicChemistryNotificationBinarySensor(ScreenLogicBinarySensor):
    """Representation of a ScreenLogic IntelliChem notification binary sensor entity."""

    @property
    def sensor(self):
        """Shortcut to access the sensor data."""
        return self.coordinator.data[SL_DATA.KEY_CHEMISTRY][SL_DATA.KEY_NOTIFICATIONS][
            self._data_key
        ]


class ScreenlogicSCGBinarySensor(ScreenLogicBinarySensor):
    """Representation of a ScreenLogic SCG binary sensor entity."""

    @property
    def sensor(self):
        """Shortcut to access the sensor data."""
        return self.coordinator.data[SL_DATA.KEY_SCG][self._data_key]


class ScreenlogicConfigBinarySensor(ScreenLogicBinarySensor):
    """Representation of a ScreenLogic config data binary sensor entity."""

    @property
    def sensor(self):
        """Shortcut to access the sensor data."""
        return self.coordinator.data[SL_DATA.KEY_CONFIG][self._data_key]
