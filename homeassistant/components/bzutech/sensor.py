"""Sensor for BZUTech integration."""

from datetime import timedelta

from bzutech import BzuTech

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfSoundPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONF_CHIPID, CONF_ENDPOINT, CONF_SENSORPORT, DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)

SENSOR_TYPE: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="TMP",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="HUM",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="VOT",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="CO2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="CUR",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="LUM",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="PIR",
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="DOOR",
        translation_key="door",
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="DOR",
        translation_key="door",
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="M10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="M25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="M40",
        translation_key="pm40",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="SND",
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="M01",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="C01",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="VOC",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="DOS",
        translation_key="door",
        device_class=SensorDeviceClass.AQI,
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="VOA",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="VOB",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="CRA",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="CRB",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="CRC",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="VRA",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="VRB",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="VRC",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="C05",
        translation_key="pm05",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="C25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="C40",
        translation_key="pm40",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="C10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="BAT",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="DBM",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="MEM",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.KILOBYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="UPT",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

ENDPOINT_SENSORS = {
    "EP101": ["SHT20-TMP", "SHT20-HUM", "BH1750-LUM"],
    "EP111": ["SHT20-TMP", "SHT20-HUM", "BH1750-LUM", "SHT30-TMP", "SHT30-HUM"],
    "EP121": ["SHT20-TMP", "SHT20-HUM", "BH1750-LUM", "DOOR-DOR"],
    "EP200": [
        "SHT20-TMP",
        "SHT20-HUM",
        "SGP30-VOC",
        "SGP30-CO2",
        "SPS30-M01",
        "SPS30-M25",
        "SPS30-M40",
        "SPS30-M10",
    ],
    "EP300": ["RTZSBZ-SND"],
    "EP400": [
        "ADS7878-VRA",
        "ADS7878-VRB",
        "ADS7878-VRC",
        "ADS7878-CRA",
        "ADS7878-CRB",
        "ADS7878-CRC",
        "ADS7878-CRN",
        "ADS7878-APA",
        "ADS7878-APB",
        "ADS7878-APC",
        "ADS7878-PPA",
        "ADS7878-PPB",
        "ADS7878-PPC",
        "ADS7878-RPA",
        "ADS7878-RPB",
        "ADS7878-RPC",
        "ADS7878-ACA",
        "ADS7878-BCA",
        "ADS7878-CCA",
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Do entry Setup."""
    bzu_api = hass.data[DOMAIN][entry.entry_id]
    sensors = [
        BzuSensorEntity(
            bzu_api, f"{sensor}-{entry.data[CONF_SENSORPORT]}", entry, description
        )
        for sensor in ENDPOINT_SENSORS[entry.data[CONF_ENDPOINT]]
        for description in SENSOR_TYPE
        if description.key == sensor.split("-")[1]
    ]

    async_add_entities(sensors, update_before_add=True)


class BzuSensorEntity(SensorEntity):
    """Setup sensor entity."""

    has_entity_name = True

    def __init__(
        self,
        api: BzuTech,
        sensorname: str,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Do Sensor configuration."""
        self._attr_unique_id = (
            entry.data[CONF_CHIPID]
            + sensorname.split("-")[1]
            + entry.data[CONF_SENSORPORT]
        )
        self.chipid = entry.data[CONF_CHIPID]
        self.sensorname = sensorname
        self.name = sensorname.split("-")[1]
        self.api: BzuTech = api
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_device_info = DeviceInfo(
            name=f"{self.chipid}-{entry.data[CONF_SENSORPORT]}",
            identifiers={(DOMAIN, f"ESP-{self.chipid}")},
            entry_type=DeviceEntryType("service"),
            manufacturer="Bzu Tech",
            model=f"ESP-{self.chipid}-{entry.data[CONF_SENSORPORT]}",
            serial_number=f"{self.chipid}P{entry.data[CONF_SENSORPORT]}",
        )

    async def async_update(self) -> None:
        """Update entity values, the bzutech webapi does not have a endpoint to get every sensor value at once, so each entity need to poll."""
        try:
            self._attr_native_value = await self.api.get_reading(
                str(self.chipid), self.sensorname
            )
        except (KeyError, TypeError) as error:
            await self.api.start()
            raise UpdateFailed(error) from error
