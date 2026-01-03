"""Support for Tuya binary sensors."""

from __future__ import annotations

from dataclasses import dataclass

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity
from .models import DPCodeBitmapBitWrapper, DPCodeBooleanWrapper, DPCodeWrapper


@dataclass(frozen=True)
class TuyaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Tuya binary sensor."""

    # DPCode, to use. If None, the key will be used as DPCode
    dpcode: DPCode | None = None

    # Value or values to consider binary sensor to be "on"
    on_value: bool | float | int | str | set[bool | float | int | str] = True

    # For DPType.BITMAP, the bitmap_key is used to extract the bit mask
    bitmap_key: str | None = None


# Commonly used sensors
TAMPER_BINARY_SENSOR = TuyaBinarySensorEntityDescription(
    key=DPCode.TEMPER_ALARM,
    name="Tamper",
    device_class=BinarySensorDeviceClass.TAMPER,
    entity_category=EntityCategory.DIAGNOSTIC,
)


# All descriptions can be found here. Mostly the Boolean data types in the
# default status set of each category (that don't have a set instruction)
# end up being a binary sensor.
BINARY_SENSORS: dict[DeviceCategory, tuple[TuyaBinarySensorEntityDescription, ...]] = {
    DeviceCategory.CO2BJ: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.CO2_STATE,
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.COBJ: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.CO_STATE,
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="1",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.CO_STATUS,
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.CS: (
        TuyaBinarySensorEntityDescription(
            key="tankfull",
            dpcode=DPCode.FAULT,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            bitmap_key="tankfull",
            translation_key="tankfull",
        ),
        TuyaBinarySensorEntityDescription(
            key="defrost",
            dpcode=DPCode.FAULT,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            bitmap_key="defrost",
            translation_key="defrost",
        ),
        TuyaBinarySensorEntityDescription(
            key="wet",
            dpcode=DPCode.FAULT,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            bitmap_key="wet",
            translation_key="wet",
        ),
    ),
    DeviceCategory.CWWSQ: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.FEED_STATE,
            translation_key="feeding",
            on_value="feeding",
        ),
    ),
    DeviceCategory.DGNBJ: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.GAS_SENSOR_STATE,
            device_class=BinarySensorDeviceClass.GAS,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.CH4_SENSOR_STATE,
            translation_key="methane",
            device_class=BinarySensorDeviceClass.GAS,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.VOC_STATE,
            translation_key="voc",
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.PM25_STATE,
            translation_key="pm25",
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.CO_STATE,
            translation_key="carbon_monoxide",
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.CO2_STATE,
            translation_key="carbon_dioxide",
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.CH2O_STATE,
            translation_key="formaldehyde",
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.DOORCONTACT_STATE,
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.WATERSENSOR_STATE,
            device_class=BinarySensorDeviceClass.MOISTURE,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.PRESSURE_STATE,
            translation_key="pressure",
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.SMOKE_SENSOR_STATE,
            device_class=BinarySensorDeviceClass.SMOKE,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.HPS: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PRESENCE_STATE,
            device_class=BinarySensorDeviceClass.OCCUPANCY,
            on_value={"presence", "small_move", "large_move", "peaceful"},
        ),
    ),
    DeviceCategory.JQBJ: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.CH2O_STATE,
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.JWBJ: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.CH4_SENSOR_STATE,
            device_class=BinarySensorDeviceClass.GAS,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.LDCG: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.TEMPER_ALARM,
            device_class=BinarySensorDeviceClass.TAMPER,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.MC: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.STATUS,
            device_class=BinarySensorDeviceClass.DOOR,
            on_value={"open", "opened"},
        ),
    ),
    DeviceCategory.MCS: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.DOORCONTACT_STATE,
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.SWITCH,  # Used by non-standard contact sensor implementations
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.MK: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.CLOSED_OPENED_KIT,
            device_class=BinarySensorDeviceClass.LOCK,
            on_value={"AQAB"},
        ),
    ),
    DeviceCategory.MSP: (
        TuyaBinarySensorEntityDescription(
            key=f"{DPCode.FAULT}_full_fault",
            dpcode=DPCode.FAULT,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            bitmap_key="full_fault",
            translation_key="bag_full",
        ),
        TuyaBinarySensorEntityDescription(
            key=f"{DPCode.FAULT}_box_out",
            dpcode=DPCode.FAULT,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            bitmap_key="box_out",
            translation_key="cover_off",
        ),
    ),
    DeviceCategory.PIR: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PIR,
            device_class=BinarySensorDeviceClass.MOTION,
            on_value="pir",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.PM2_5: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PM25_STATE,
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.QXJ: (TAMPER_BINARY_SENSOR,),
    DeviceCategory.RQBJ: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.GAS_SENSOR_STATUS,
            device_class=BinarySensorDeviceClass.GAS,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.GAS_SENSOR_STATE,
            device_class=BinarySensorDeviceClass.GAS,
            on_value="1",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.SGBJ: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.CHARGE_STATE,
            device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.SJ: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.WATERSENSOR_STATE,
            device_class=BinarySensorDeviceClass.MOISTURE,
            on_value={"1", "alarm"},
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.SOS: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.SOS_STATE,
            device_class=BinarySensorDeviceClass.SAFETY,
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.VOC: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.VOC_STATE,
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.WG2: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.MASTER_STATE,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            on_value="alarm",
        ),
    ),
    DeviceCategory.WK: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.VALVE_STATE,
            translation_key="valve",
            on_value="open",
        ),
    ),
    DeviceCategory.WKF: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.WINDOW_STATE,
            device_class=BinarySensorDeviceClass.WINDOW,
            on_value="opened",
        ),
    ),
    DeviceCategory.WSDCG: (TAMPER_BINARY_SENSOR,),
    DeviceCategory.YLCG: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PRESSURE_STATE,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.YWBJ: (
        TuyaBinarySensorEntityDescription(
            key=DPCode.SMOKE_SENSOR_STATUS,
            device_class=BinarySensorDeviceClass.SMOKE,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.SMOKE_SENSOR_STATE,
            device_class=BinarySensorDeviceClass.SMOKE,
            on_value={"1", "alarm"},
        ),
        TAMPER_BINARY_SENSOR,
    ),
    DeviceCategory.ZD: (
        TuyaBinarySensorEntityDescription(
            key=f"{DPCode.SHOCK_STATE}_vibration",
            dpcode=DPCode.SHOCK_STATE,
            device_class=BinarySensorDeviceClass.VIBRATION,
            on_value="vibration",
        ),
        TuyaBinarySensorEntityDescription(
            key=f"{DPCode.SHOCK_STATE}_drop",
            dpcode=DPCode.SHOCK_STATE,
            translation_key="drop",
            on_value="drop",
        ),
        TuyaBinarySensorEntityDescription(
            key=f"{DPCode.SHOCK_STATE}_tilt",
            dpcode=DPCode.SHOCK_STATE,
            translation_key="tilt",
            on_value="tilt",
        ),
    ),
}


class _CustomDPCodeWrapper(DPCodeWrapper):
    """Custom DPCode Wrapper to check for values in a set."""

    _valid_values: set[bool | float | int | str]

    def __init__(
        self, dpcode: str, valid_values: set[bool | float | int | str]
    ) -> None:
        """Init CustomDPCodeBooleanWrapper."""
        super().__init__(dpcode)
        self._valid_values = valid_values

    def read_device_status(self, device: CustomerDevice) -> bool | None:
        """Read the device value for the dpcode."""
        if (raw_value := device.status.get(self.dpcode)) is None:
            return None
        return raw_value in self._valid_values


def _get_dpcode_wrapper(
    device: CustomerDevice,
    description: TuyaBinarySensorEntityDescription,
) -> DPCodeWrapper | None:
    """Get DPCode wrapper for an entity description."""
    dpcode = description.dpcode or description.key
    if description.bitmap_key is not None:
        return DPCodeBitmapBitWrapper.find_dpcode(
            device, dpcode, bitmap_key=description.bitmap_key
        )

    if bool_type := DPCodeBooleanWrapper.find_dpcode(device, dpcode):
        return bool_type

    # Legacy / compatibility
    if dpcode not in device.status:
        return None
    return _CustomDPCodeWrapper(
        dpcode,
        description.on_value
        if isinstance(description.on_value, set)
        else {description.on_value},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        entities: list[TuyaBinarySensorEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := BINARY_SENSORS.get(device.category):
                entities.extend(
                    TuyaBinarySensorEntity(device, manager, description, dpcode_wrapper)
                    for description in descriptions
                    if (dpcode_wrapper := _get_dpcode_wrapper(device, description))
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaBinarySensorEntity(TuyaEntity, BinarySensorEntity):
    """Tuya Binary Sensor Entity."""

    entity_description: TuyaBinarySensorEntityDescription

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaBinarySensorEntityDescription,
        dpcode_wrapper: DPCodeWrapper,
    ) -> None:
        """Init Tuya binary sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._dpcode_wrapper = dpcode_wrapper

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self._read_wrapper(self._dpcode_wrapper)
