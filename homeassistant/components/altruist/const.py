"""Constants for the Altruist Sensor integration."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfTemperature,
)

DOMAIN = "altruist"
NAME = "Altruist Sensor"
UPDATE_INTERVAL = 15

# Sensors
SENSOR_BME280_HUMIDITY = "BME280_humidity"
SENSOR_BME280_PRESSURE = "BME280_pressure"
SENSOR_BME280_TEMPERATURE = "BME280_temperature"
SENSOR_BMP_PRESSURE = "BMP_pressure"
SENSOR_BMP_TEMPERATURE = "BMP_temperature"
SENSOR_BMP280_PRESSURE = "BMP280_pressure"
SENSOR_BMP280_TEMPERATURE = "BMP280_temperature"
SENSOR_DS18B20_TEMPERATURE = "DS18B20_temperature"
SENSOR_HECA_HUMIDITY = "HECA_humidity"
SENSOR_HECA_TEMPERATURE = "HECA_temperature"
SENSOR_HPM_P1 = "HPM_P1"
SENSOR_HPM_P2 = "HPM_P2"
SENSOR_HTU21D_HUMIDITY = "HTU21D_humidity"
SENSOR_HTU21D_TEMPERATURE = "HTU21D_temperature"
SENSOR_HUMIDITY = "humidity"
SENSOR_PM1 = "SDS_P1"
SENSOR_PM2 = "SDS_P2"
SENSOR_PMS_P0 = "PMS_P0"
SENSOR_PMS_P1 = "PMS_P1"
SENSOR_PMS_P2 = "PMS_P2"
SENSOR_SHT3X_HUMIDITY = "SHT3X_humidity"
SENSOR_SHT3X_TEMPERATURE = "SHT3X_temperature"
SENSOR_SPS30_P0 = "SPS30_P0"
SENSOR_SPS30_P1 = "SPS30_P1"
SENSOR_SPS30_P2 = "SPS30_P2"
SENSOR_SPS30_P4 = "SPS30_P4"
SENSOR_SEN5X_P0 = "SEN5X_P0"
SENSOR_SEN5X_P1 = "SEN5X_P1"
SENSOR_SEN5X_P2 = "SEN5X_P2"
SENSOR_SEN5X_P4 = "SEN5X_P4"
SENSOR_SEN5X_NOX = "SEN5X_NOX"
SENSOR_SEN5X_VOC = "SEN5X_VOC"
SENSOR_TEMPERATURE = "temperature"
SENSOR_WIFI_SIGNAL = "signal"
SENSOR_NOISE_MAX = "PCBA_noiseMax"
SENSOR_NOISE_AVG = "PCBA_noiseAvg"
SENSOR_CCS811_CO2 = "CCS_CO2"
SENSOR_CCS8111_TVOC = "CCS_TVOC"
SENSOR_RADIATION = "GC"
SENSOR_SCD4X_CO2 = "SCD4x_co2"

SENSOR_DESCRIPTIONS = {
    SENSOR_BME280_HUMIDITY: SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key=SENSOR_BME280_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_BME280_PRESSURE: SensorEntityDescription(
        device_class=SensorDeviceClass.PRESSURE,
        key=SENSOR_BME280_PRESSURE,
        name="Pressure",
        native_unit_of_measurement=UnitOfPressure.PA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_BME280_TEMPERATURE: SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=SENSOR_BME280_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_BMP_PRESSURE: SensorEntityDescription(
        device_class=SensorDeviceClass.PRESSURE,
        key=SENSOR_BMP_PRESSURE,
        name="Pressure",
        native_unit_of_measurement=UnitOfPressure.PA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_BMP_TEMPERATURE: SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=SENSOR_BMP_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_BMP280_TEMPERATURE: SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=SENSOR_BMP280_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_BMP280_PRESSURE: SensorEntityDescription(
        device_class=SensorDeviceClass.PRESSURE,
        key=SENSOR_BMP280_PRESSURE,
        name="Pressure",
        native_unit_of_measurement=UnitOfPressure.PA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_DS18B20_TEMPERATURE: SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=SENSOR_DS18B20_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_HECA_HUMIDITY: SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key=SENSOR_HECA_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_HECA_TEMPERATURE: SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=SENSOR_HECA_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_HPM_P1: SensorEntityDescription(
        device_class=SensorDeviceClass.PM10,
        key=SENSOR_HPM_P1,
        name="PM10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_HPM_P2: SensorEntityDescription(
        device_class=SensorDeviceClass.PM25,
        key=SENSOR_HPM_P2,
        name="PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_HTU21D_HUMIDITY: SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key=SENSOR_HTU21D_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_HTU21D_TEMPERATURE: SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=SENSOR_HTU21D_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_HUMIDITY: SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key=SENSOR_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_PM1: SensorEntityDescription(
        device_class=SensorDeviceClass.PM10,
        key=SENSOR_PM1,
        name="PM10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_PM2: SensorEntityDescription(
        device_class=SensorDeviceClass.PM25,
        key=SENSOR_PM2,
        name="PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_PMS_P0: SensorEntityDescription(
        device_class=SensorDeviceClass.PM1,
        key=SENSOR_PMS_P0,
        name="PM1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_PMS_P1: SensorEntityDescription(
        device_class=SensorDeviceClass.PM10,
        key=SENSOR_PMS_P1,
        name="PM10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_PMS_P2: SensorEntityDescription(
        device_class=SensorDeviceClass.PM25,
        key=SENSOR_PMS_P2,
        name="PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SHT3X_HUMIDITY: SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key=SENSOR_SHT3X_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SHT3X_TEMPERATURE: SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=SENSOR_SHT3X_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SPS30_P0: SensorEntityDescription(
        device_class=SensorDeviceClass.PM1,
        key=SENSOR_SPS30_P0,
        name="PM1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SPS30_P1: SensorEntityDescription(
        device_class=SensorDeviceClass.PM10,
        key=SENSOR_SPS30_P1,
        name="PM10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SPS30_P2: SensorEntityDescription(
        device_class=SensorDeviceClass.PM25,
        key=SENSOR_SPS30_P2,
        name="PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SPS30_P4: SensorEntityDescription(
        device_class=SensorDeviceClass.PM25,  # SensorDeviceClass.PM4 not supported.
        key=SENSOR_SPS30_P4,
        name="PM4",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SEN5X_P0: SensorEntityDescription(
        device_class=SensorDeviceClass.PM1,
        key=SENSOR_SEN5X_P0,
        name="PM1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SEN5X_P1: SensorEntityDescription(
        device_class=SensorDeviceClass.PM10,
        key=SENSOR_SEN5X_P1,
        name="PM10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SEN5X_P2: SensorEntityDescription(
        device_class=SensorDeviceClass.PM25,
        key=SENSOR_SEN5X_P2,
        name="PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SEN5X_P4: SensorEntityDescription(
        device_class=SensorDeviceClass.PM25,  # SensorDeviceClass.PM4 not supported.
        key=SENSOR_SEN5X_P4,
        name="PM4",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SEN5X_NOX: SensorEntityDescription(
        device_class=SensorDeviceClass.AQI,
        # SensorDeviceClass.NOX_INDEX is not supported
        # SensorDeviceClass.NITROGEN_MONOXIDE and .NITROGEN_DIOXIDE are supported, but require a unit of ug/m3 which is not appropriate for a unitless index
        key=SENSOR_SEN5X_NOX,
        name="NOX",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SEN5X_VOC: SensorEntityDescription(
        device_class=SensorDeviceClass.AQI,
        # SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_INDEX is not supported
        # SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS is supported, but requires a unit of ug/m3 which is not appropriate for a unitless index
        key=SENSOR_SEN5X_VOC,
        name="VOC",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_TEMPERATURE: SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=SENSOR_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_WIFI_SIGNAL: SensorEntityDescription(
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        key=SENSOR_WIFI_SIGNAL,
        name="WiFi signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SENSOR_NOISE_MAX: SensorEntityDescription(
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        key=SENSOR_NOISE_MAX,
        name="Maximum Noise",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_NOISE_AVG: SensorEntityDescription(
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        key=SENSOR_NOISE_AVG,
        name="Average Noise",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_CCS811_CO2: SensorEntityDescription(
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        key=SENSOR_CCS811_CO2,
        name="CO2",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_CCS8111_TVOC: SensorEntityDescription(
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        key=SENSOR_CCS8111_TVOC,
        name="TVOC",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_RADIATION: SensorEntityDescription(
        device_class=SensorDeviceClass.IRRADIANCE,
        key=SENSOR_RADIATION,
        native_unit_of_measurement="μR/h",
        name="Radiation",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SENSOR_SCD4X_CO2: SensorEntityDescription(
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        key=SENSOR_SCD4X_CO2,
        name="CO2",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}
