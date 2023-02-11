"""Support for Tuya binary sensors."""
from __future__ import annotations

from dataclasses import dataclass

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode


@dataclass
class TuyaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Tuya binary sensor."""

    # DPCode, to use. If None, the key will be used as DPCode
    dpcode: DPCode | None = None

    # Value or values to consider binary sensor to be "on"
    on_value: bool | float | int | str | set[bool | float | int | str] = True


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
            name="Gas",
            icon="mdi:gas-cylinder",
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.CH4_SENSOR_STATE,
            name="Methane",
            device_class=BinarySensorDeviceClass.GAS,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.VOC_STATE,
            name="Volatile organic compound",
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.PM25_STATE,
            name="Particulate matter 2.5 µm",
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.CO_STATE,
            name="Carbon monoxide",
            icon="mdi:molecule-co",
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.CO2_STATE,
            icon="mdi:molecule-co2",
            name="Carbon dioxide",
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.CH2O_STATE,
            name="Formaldehyde",
            device_class=BinarySensorDeviceClass.SAFETY,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.DOORCONTACT_STATE,
            name="Door",
            device_class=BinarySensorDeviceClass.DOOR,
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.WATERSENSOR_STATE,
            name="Water leak",
            device_class=BinarySensorDeviceClass.MOISTURE,
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.PRESSURE_STATE,
            name="Pressure",
            on_value="alarm",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.SMOKE_SENSOR_STATE,
            name="Smoke",
            icon="mdi:smoke-detector",
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
            name="Feeding",
            icon="mdi:information",
            on_value="feeding",
        ),
    ),
    # Human Presence Sensor
    # https://developer.tuya.com/en/docs/iot/categoryhps?id=Kaiuz42yhn1hs
    "hps": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PRESENCE_STATE,
            device_class=BinarySensorDeviceClass.MOTION,
            on_value="presence",
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
            name="Tamper",
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
            name="Window",
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
            on_value="1",
        ),
        TAMPER_BINARY_SENSOR,
    ),
    # Vibration Sensor
    # https://developer.tuya.com/en/docs/iot/categoryzd?id=Kaiuz3a5vrzno
    "zd": (
        TuyaBinarySensorEntityDescription(
            key=f"{DPCode.SHOCK_STATE}_vibration",
            dpcode=DPCode.SHOCK_STATE,
            name="Vibration",
            device_class=BinarySensorDeviceClass.VIBRATION,
            on_value="vibration",
        ),
        TuyaBinarySensorEntityDescription(
            key=f"{DPCode.SHOCK_STATE}_drop",
            dpcode=DPCode.SHOCK_STATE,
            name="Drop",
            icon="mdi:icon=package-down",
            on_value="drop",
        ),
        TuyaBinarySensorEntityDescription(
            key=f"{DPCode.SHOCK_STATE}_tilt",
            dpcode=DPCode.SHOCK_STATE,
            name="Tilt",
            icon="mdi:spirit-level",
            on_value="tilt",
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        entities: list[TuyaBinarySensorEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := BINARY_SENSORS.get(device.category):
                for description in descriptions:
                    dpcode = description.dpcode or description.key
                    if dpcode in device.status:
                        entities.append(
                            TuyaBinarySensorEntity(
                                device, hass_data.device_manager, description
                            )
                        )

        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaBinarySensorEntity(TuyaEntity, BinarySensorEntity):
    """Tuya Binary Sensor Entity."""

    entity_description: TuyaBinarySensorEntityDescription

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
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

        return self.device.status[dpcode] == self.entity_description.on_value
