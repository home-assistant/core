"""Support for Tuya binary sensors."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
import json

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TuyaConfigEntry
from .const import LOGGER, TUYA_DISCOVERY_NEW, DPCode
from .entity import TuyaEntity


@dataclass(frozen=True)
class BitTest:
    """BitTest is used to encode the "on_value" for one bit in a bitmask.

    The mask is used to isolate the bit that should be
    tested. By default, 1 means "on" and 0 means "off", but setting the
    bit in xmask flips it so that 1 means "off" and 0 means "on".
    """

    mask: int = 0
    xmask: int = 0


@dataclass(frozen=True)
class TuyaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Tuya binary sensor."""

    # DPCode, to use. If None, the key will be used as DPCode
    dpcode: DPCode | None = None

    # Value or values to consider binary sensor to be "on"
    on_value: bool | float | int | str | BitTest | set[bool | float | int | str] = True


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
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
BINARY_SENSORS: dict[str, tuple[TuyaBinarySensorEntityDescription, ...]] = {
    # Multi-functional Sensor
    # https://developer.tuya.com/en/docs/iot/categorydgnbj?id=Kaiuz3yorvzg3
    "dgnbj": (
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
    # CO2 Detector
    # https://developer.tuya.com/en/docs/iot/categoryco2bj?id=Kaiuz3wes7yuy
    "co2bj": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.CO2_STATE,
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    # CO Detector
    # https://developer.tuya.com/en/docs/iot/categorycobj?id=Kaiuz3u1j6q1v
    "cobj": (
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
    # Smart Pet Feeder
    # https://developer.tuya.com/en/docs/iot/categorycwwsq?id=Kaiuz2b6vydld
    "cwwsq": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.FEED_STATE,
            translation_key="feeding",
            on_value="feeding",
        ),
    ),
    # Human Presence Sensor
    # https://developer.tuya.com/en/docs/iot/categoryhps?id=Kaiuz42yhn1hs
    "hps": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PRESENCE_STATE,
            device_class=BinarySensorDeviceClass.OCCUPANCY,
            on_value={"presence", "small_move", "large_move", "peaceful"},
        ),
    ),
    # Formaldehyde Detector
    # Note: Not documented
    "jqbj": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.CH2O_STATE,
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    # Methane Detector
    # https://developer.tuya.com/en/docs/iot/categoryjwbj?id=Kaiuz40u98lkm
    "jwbj": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.CH4_SENSOR_STATE,
            device_class=BinarySensorDeviceClass.GAS,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    # Door and Window Controller
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48r5zjsy9
    "mc": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.STATUS,
            device_class=BinarySensorDeviceClass.DOOR,
            on_value={"open", "opened"},
        ),
    ),
    # Door Window Sensor
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48hm02l8m
    "mcs": (
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
    # Access Control
    # https://developer.tuya.com/en/docs/iot/s?id=Kb0o2xhlkxbet
    "mk": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.CLOSED_OPENED_KIT,
            device_class=BinarySensorDeviceClass.LOCK,
            on_value={"AQAB"},
        ),
    ),
    # Luminance Sensor
    # https://developer.tuya.com/en/docs/iot/categoryldcg?id=Kaiuz3n7u69l8
    "ldcg": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.TEMPER_ALARM,
            device_class=BinarySensorDeviceClass.TAMPER,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        TAMPER_BINARY_SENSOR,
    ),
    # PIR Detector
    # https://developer.tuya.com/en/docs/iot/categorypir?id=Kaiuz3ss11b80
    "pir": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PIR,
            device_class=BinarySensorDeviceClass.MOTION,
            on_value="pir",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    # PM2.5 Sensor
    # https://developer.tuya.com/en/docs/iot/categorypm25?id=Kaiuz3qof3yfu
    "pm2.5": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PM25_STATE,
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    # Gas Detector
    # https://developer.tuya.com/en/docs/iot/categoryrqbj?id=Kaiuz3d162ubw
    "rqbj": (
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
    # Water Detector
    # https://developer.tuya.com/en/docs/iot/categorysj?id=Kaiuz3iub2sli
    "sj": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.WATERSENSOR_STATE,
            device_class=BinarySensorDeviceClass.MOISTURE,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    # Emergency Button
    # https://developer.tuya.com/en/docs/iot/categorysos?id=Kaiuz3oi6agjy
    "sos": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.SOS_STATE,
            device_class=BinarySensorDeviceClass.SAFETY,
        ),
        TAMPER_BINARY_SENSOR,
    ),
    # Volatile Organic Compound Sensor
    # Note: Undocumented in cloud API docs, based on test device
    "voc": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.VOC_STATE,
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    # Thermostatic Radiator Valve
    # Not documented
    "wkf": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.WINDOW_STATE,
            device_class=BinarySensorDeviceClass.WINDOW,
            on_value="opened",
        ),
    ),
    # Temperature and Humidity Sensor
    # https://developer.tuya.com/en/docs/iot/categorywsdcg?id=Kaiuz3hinij34
    "wsdcg": (TAMPER_BINARY_SENSOR,),
    # Pressure Sensor
    # https://developer.tuya.com/en/docs/iot/categoryylcg?id=Kaiuz3kc2e4gm
    "ylcg": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PRESSURE_STATE,
            on_value="alarm",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    # Smoke Detector
    # https://developer.tuya.com/en/docs/iot/categoryywbj?id=Kaiuz3f6sf952
    "ywbj": (
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
    # Vibration Sensor
    # https://developer.tuya.com/en/docs/iot/categoryzd?id=Kaiuz3a5vrzno
    "zd": (
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


# Sometimes bitmaps are used to pack the status of several binary sensors
# into one integer. In the home assistant interface, it is more convenient
# to represent each bit of the bitmap as a separate binary sensor. So
# each TuyaBitmapSensorEntityDescription gets converted into several
# TuyaBinarySensorEntityDescription's during async_discover_device.
@dataclass(frozen=True)
class TuyaBitmapSensorEntityDescription(TuyaBinarySensorEntityDescription):
    """Describes a Tuya bitmap sensor."""

    # Which bits to convert into binary sensors
    mask: int = 0

    # By default, if a bit is 1 it means "on" and 0 means "off". But
    # sometimes the meaning might be inverted, so 1 means "off" and 0
    # means "on". Setting a bit in xmask inverts the meaning of that
    # bit.
    xmask: int = 0


BITMAP_SENSORS: dict[str, tuple[TuyaBitmapSensorEntityDescription, ...]] = {
    # Dehumidifier (however, these bitmap values are currently undocumented)
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48r6jke8e
    "cs": (
        TuyaBitmapSensorEntityDescription(
            key=DPCode.FAULT,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            mask=0x83,  # tankfull, defrost, wet
            xmask=0x0,
        ),
    ),
}


def generate_binary_sensor_entities(
    device: CustomerDevice, manager: Manager
) -> Generator[TuyaBinarySensorEntity]:
    """Generate a list of binary sensors for the device."""
    for description in BINARY_SENSORS.get(device.category, []):
        dpcode = description.dpcode or description.key
        if dpcode in device.status:
            yield TuyaBinarySensorEntity(device, manager, description)

    for description in BITMAP_SENSORS.get(device.category, []):
        dpcode = DPCode(description.dpcode or description.key)
        if dpcode not in device.status:
            continue
        try:
            status_range = device.status_range[dpcode]
            labels = json.loads(status_range.values)["label"]
            assert status_range.type == "Bitmap"
            for i, label in enumerate(labels):
                xi = 1 << i
                if (xi & description.mask) == 0:
                    continue
                yield TuyaBinarySensorEntity(
                    device,
                    manager,
                    TuyaBinarySensorEntityDescription(
                        key=f"{dpcode}_{label}",
                        dpcode=dpcode,
                        translation_key=label,
                        device_class=description.device_class,
                        entity_category=description.entity_category,
                        on_value=BitTest(mask=xi, xmask=description.xmask & xi),
                        name=label,
                    ),
                )
        except (AssertionError, IndexError, ValueError):
            LOGGER.exception("Invalid Bitmap device: %s", str(device))


async def async_setup_entry(
    hass: HomeAssistant, entry: TuyaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        entities: list[TuyaBinarySensorEntity] = []
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            entities.extend(generate_binary_sensor_entities(device, hass_data.manager))

        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

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
    ) -> None:
        """Init Tuya binary sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        dpcode = self.entity_description.dpcode or self.entity_description.key
        if dpcode not in self.device.status:
            return False

        if isinstance(self.entity_description.on_value, set):
            return self.device.status[dpcode] in self.entity_description.on_value

        if isinstance(self.entity_description.on_value, BitTest):
            bitmap = self.device.status[dpcode]
            mask = self.entity_description.on_value.mask
            xmask = self.entity_description.on_value.xmask
            return ((bitmap ^ xmask) & mask) != 0

        return self.device.status[dpcode] == self.entity_description.on_value
