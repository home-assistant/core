"""Support for a ScreenLogic Binary Sensor."""
from screenlogicpy.const import CODE, DATA as SL_DATA, DEVICE_TYPE, EQUIPMENT, ON_OFF

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ScreenlogicDataUpdateCoordinator
from .const import DOMAIN
from .entity import ScreenlogicEntity, ScreenLogicPushEntity

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
    entities: list[ScreenLogicBinarySensorEntity] = []
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    gateway_data = coordinator.gateway_data
    config = gateway_data[SL_DATA.KEY_CONFIG]

    # Generic binary sensor
    entities.append(
        ScreenLogicStatusBinarySensor(coordinator, "chem_alarm", CODE.STATUS_CHANGED)
    )

    entities.extend(
        [
            ScreenlogicConfigBinarySensor(coordinator, cfg_sensor, CODE.STATUS_CHANGED)
            for cfg_sensor in config
            if cfg_sensor in SUPPORTED_CONFIG_BINARY_SENSORS
        ]
    )

    if config["equipment_flags"] & EQUIPMENT.FLAG_INTELLICHEM:
        chemistry = gateway_data[SL_DATA.KEY_CHEMISTRY]
        # IntelliChem alarm sensors
        entities.extend(
            [
                ScreenlogicChemistryAlarmBinarySensor(
                    coordinator, chem_alarm, CODE.CHEMISTRY_CHANGED
                )
                for chem_alarm in chemistry[SL_DATA.KEY_ALERTS]
                if not chem_alarm.startswith("_")
            ]
        )

        # Intellichem notification sensors
        entities.extend(
            [
                ScreenlogicChemistryNotificationBinarySensor(
                    coordinator, chem_notif, CODE.CHEMISTRY_CHANGED
                )
                for chem_notif in chemistry[SL_DATA.KEY_NOTIFICATIONS]
                if not chem_notif.startswith("_")
            ]
        )

    if config["equipment_flags"] & EQUIPMENT.FLAG_CHLORINATOR:
        # SCG binary sensor
        entities.append(ScreenlogicSCGBinarySensor(coordinator, "scg_status"))

    async_add_entities(entities)


class ScreenLogicBinarySensorEntity(ScreenlogicEntity, BinarySensorEntity):
    """Base class for all ScreenLogic binary sensor entities."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self) -> str | None:
        """Return the sensor name."""
        return self.sensor["name"]

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device class."""
        device_type = self.sensor.get("device_type")
        return SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS.get(device_type)

    @property
    def is_on(self) -> bool:
        """Determine if the sensor is on."""
        return self.sensor["value"] == ON_OFF.ON

    @property
    def sensor(self) -> dict:
        """Shortcut to access the sensor data."""
        return self.gateway_data[SL_DATA.KEY_SENSORS][self._data_key]


class ScreenLogicStatusBinarySensor(
    ScreenLogicBinarySensorEntity, ScreenLogicPushEntity
):
    """Representation of a basic ScreenLogic sensor entity."""


class ScreenlogicChemistryAlarmBinarySensor(
    ScreenLogicBinarySensorEntity, ScreenLogicPushEntity
):
    """Representation of a ScreenLogic IntelliChem alarm binary sensor entity."""

    @property
    def sensor(self) -> dict:
        """Shortcut to access the sensor data."""
        return self.gateway_data[SL_DATA.KEY_CHEMISTRY][SL_DATA.KEY_ALERTS][
            self._data_key
        ]


class ScreenlogicChemistryNotificationBinarySensor(
    ScreenLogicBinarySensorEntity, ScreenLogicPushEntity
):
    """Representation of a ScreenLogic IntelliChem notification binary sensor entity."""

    @property
    def sensor(self) -> dict:
        """Shortcut to access the sensor data."""
        return self.gateway_data[SL_DATA.KEY_CHEMISTRY][SL_DATA.KEY_NOTIFICATIONS][
            self._data_key
        ]


class ScreenlogicSCGBinarySensor(ScreenLogicBinarySensorEntity):
    """Representation of a ScreenLogic SCG binary sensor entity."""

    @property
    def sensor(self) -> dict:
        """Shortcut to access the sensor data."""
        return self.gateway_data[SL_DATA.KEY_SCG][self._data_key]


class ScreenlogicConfigBinarySensor(
    ScreenLogicBinarySensorEntity, ScreenLogicPushEntity
):
    """Representation of a ScreenLogic config data binary sensor entity."""

    @property
    def sensor(self) -> dict:
        """Shortcut to access the sensor data."""
        return self.gateway_data[SL_DATA.KEY_CONFIG][self._data_key]
