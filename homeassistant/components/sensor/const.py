"""Constants for sensor."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

import voluptuous as vol

from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfApparentPower,
    UnitOfArea,
    UnitOfBloodGlucoseConcentration,
    UnitOfConductivity,
    UnitOfDataRate,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfEnergyDistance,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfReactivePower,
    UnitOfSoundPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
    UnitOfVolumetricFlux,
)
from homeassistant.util.unit_conversion import (
    AreaConverter,
    BaseUnitConverter,
    BloodGlucoseConcentrationConverter,
    ConductivityConverter,
    DataRateConverter,
    DistanceConverter,
    DurationConverter,
    ElectricCurrentConverter,
    ElectricPotentialConverter,
    EnergyConverter,
    EnergyDistanceConverter,
    InformationConverter,
    MassConverter,
    PowerConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
    UnitlessRatioConverter,
    VolumeConverter,
    VolumeFlowRateConverter,
)

DOMAIN: Final = "sensor"

CONF_STATE_CLASS: Final = "state_class"

ATTR_LAST_RESET: Final = "last_reset"
ATTR_STATE_CLASS: Final = "state_class"
ATTR_OPTIONS: Final = "options"


class SensorDeviceClass(StrEnum):
    """Device class for sensors."""

    # Non-numerical device classes
    DATE = "date"
    """Date.

    Unit of measurement: `None`

    ISO8601 format: https://en.wikipedia.org/wiki/ISO_8601
    """

    ENUM = "enum"
    """Enumeration.

    Provides a fixed list of options the state of the sensor can be in.

    Unit of measurement: `None`
    """

    TIMESTAMP = "timestamp"
    """Timestamp.

    Unit of measurement: `None`

    ISO8601 format: https://en.wikipedia.org/wiki/ISO_8601
    """

    # Numerical device classes, these should be aligned with NumberDeviceClass
    APPARENT_POWER = "apparent_power"
    """Apparent power.

    Unit of measurement: `VA`
    """

    AQI = "aqi"
    """Air Quality Index.

    Unit of measurement: `None`
    """

    AREA = "area"
    """Area

    Unit of measurement: `UnitOfArea` units
    """

    ATMOSPHERIC_PRESSURE = "atmospheric_pressure"
    """Atmospheric pressure.

    Unit of measurement: `UnitOfPressure` units
    """

    BATTERY = "battery"
    """Percentage of battery that is left.

    Unit of measurement: `%`
    """

    BLOOD_GLUCOSE_CONCENTRATION = "blood_glucose_concentration"
    """Blood glucose concentration.

    Unit of measurement: `mg/dL`, `mmol/L`
    """

    CO = "carbon_monoxide"
    """Carbon Monoxide gas concentration.

    Unit of measurement: `ppm` (parts per million)
    """

    CO2 = "carbon_dioxide"
    """Carbon Dioxide gas concentration.

    Unit of measurement: `ppm` (parts per million)
    """

    CONDUCTIVITY = "conductivity"
    """Conductivity.

    Unit of measurement: `S/cm`, `mS/cm`, `µS/cm`
    """

    CURRENT = "current"
    """Current.

    Unit of measurement: `A`, `mA`
    """

    DATA_RATE = "data_rate"
    """Data rate.

    Unit of measurement: UnitOfDataRate
    """

    DATA_SIZE = "data_size"
    """Data size.

    Unit of measurement: UnitOfInformation
    """

    DISTANCE = "distance"
    """Generic distance.

    Unit of measurement: `LENGTH_*` units
    - SI /metric: `mm`, `cm`, `m`, `km`
    - USCS / imperial: `in`, `ft`, `yd`, `mi`
    """

    DURATION = "duration"
    """Fixed duration.

    Unit of measurement: `d`, `h`, `min`, `s`, `ms`, `µs`
    """

    ENERGY = "energy"
    """Energy.

    Use this device class for sensors measuring energy consumption, for example
    electric energy consumption.
    Unit of measurement: `J`, `kJ`, `MJ`, `GJ`, `mWh`, `Wh`, `kWh`, `MWh`, `GWh`, `TWh`, `cal`, `kcal`, `Mcal`, `Gcal`
    """

    ENERGY_DISTANCE = "energy_distance"
    """Energy distance.

    Use this device class for sensors measuring energy by distance, for example the amount
    of electric energy consumed by an electric car.

    Unit of measurement: `kWh/100km`, `mi/kWh`, `km/kWh`
    """

    ENERGY_STORAGE = "energy_storage"
    """Stored energy.

    Use this device class for sensors measuring stored energy, for example the amount
    of electric energy currently stored in a battery or the capacity of a battery.

    Unit of measurement: `J`, `kJ`, `MJ`, `GJ`, `mWh`, `Wh`, `kWh`, `MWh`, `GWh`, `TWh`, `cal`, `kcal`, `Mcal`, `Gcal`
    """

    FREQUENCY = "frequency"
    """Frequency.

    Unit of measurement: `Hz`, `kHz`, `MHz`, `GHz`
    """

    GAS = "gas"
    """Gas.

    Unit of measurement:
    - SI / metric: `L`, `m³`
    - USCS / imperial: `ft³`, `CCF`
    """

    HUMIDITY = "humidity"
    """Relative humidity.

    Unit of measurement: `%`
    """

    ILLUMINANCE = "illuminance"
    """Illuminance.

    Unit of measurement: `lx`
    """

    IRRADIANCE = "irradiance"
    """Irradiance.

    Unit of measurement:
    - SI / metric: `W/m²`
    - USCS / imperial: `BTU/(h⋅ft²)`
    """

    MOISTURE = "moisture"
    """Moisture.

    Unit of measurement: `%`
    """

    MONETARY = "monetary"
    """Amount of money.

    Unit of measurement: ISO4217 currency code

    See https://en.wikipedia.org/wiki/ISO_4217#Active_codes for active codes
    """

    NITROGEN_DIOXIDE = "nitrogen_dioxide"
    """Amount of NO2.

    Unit of measurement: `µg/m³`
    """

    NITROGEN_MONOXIDE = "nitrogen_monoxide"
    """Amount of NO.

    Unit of measurement: `µg/m³`
    """

    NITROUS_OXIDE = "nitrous_oxide"
    """Amount of N2O.

    Unit of measurement: `µg/m³`
    """

    OZONE = "ozone"
    """Amount of O3.

    Unit of measurement: `µg/m³`
    """

    PH = "ph"
    """Potential hydrogen (acidity/alkalinity).

    Unit of measurement: Unitless
    """

    PM1 = "pm1"
    """Particulate matter <= 1 μm.

    Unit of measurement: `µg/m³`
    """

    PM10 = "pm10"
    """Particulate matter <= 10 μm.

    Unit of measurement: `µg/m³`
    """

    PM25 = "pm25"
    """Particulate matter <= 2.5 μm.

    Unit of measurement: `µg/m³`
    """

    POWER_FACTOR = "power_factor"
    """Power factor.

    Unit of measurement: `%`, `None`
    """

    POWER = "power"
    """Power.

    Unit of measurement: `mW`, `W`, `kW`, `MW`, `GW`, `TW`, `BTU/h`
    """

    PRECIPITATION = "precipitation"
    """Accumulated precipitation.

    Unit of measurement: UnitOfPrecipitationDepth
    - SI / metric: `cm`, `mm`
    - USCS / imperial: `in`
    """

    PRECIPITATION_INTENSITY = "precipitation_intensity"
    """Precipitation intensity.

    Unit of measurement: UnitOfVolumetricFlux
    - SI /metric: `mm/d`, `mm/h`
    - USCS / imperial: `in/d`, `in/h`
    """

    PRESSURE = "pressure"
    """Pressure.

    Unit of measurement:
    - `mbar`, `cbar`, `bar`
    - `Pa`, `hPa`, `kPa`
    - `inHg`
    - `psi`
    """

    REACTIVE_POWER = "reactive_power"
    """Reactive power.

    Unit of measurement: `var`, `kvar`
    """

    SIGNAL_STRENGTH = "signal_strength"
    """Signal strength.

    Unit of measurement: `dB`, `dBm`
    """

    SOUND_PRESSURE = "sound_pressure"
    """Sound pressure.

    Unit of measurement: `dB`, `dBA`
    """

    SPEED = "speed"
    """Generic speed.

    Unit of measurement: `SPEED_*` units or `UnitOfVolumetricFlux`
    - SI /metric: `mm/d`, `mm/h`, `m/s`, `km/h`, `mm/s`
    - USCS / imperial: `in/d`, `in/h`, `in/s`, `ft/s`, `mph`
    - Nautical: `kn`
    - Beaufort: `Beaufort`
    """

    SULPHUR_DIOXIDE = "sulphur_dioxide"
    """Amount of SO2.

    Unit of measurement: `µg/m³`
    """

    TEMPERATURE = "temperature"
    """Temperature.

    Unit of measurement: `°C`, `°F`, `K`
    """

    VOLATILE_ORGANIC_COMPOUNDS = "volatile_organic_compounds"
    """Amount of VOC.

    Unit of measurement: `µg/m³`
    """

    VOLATILE_ORGANIC_COMPOUNDS_PARTS = "volatile_organic_compounds_parts"
    """Ratio of VOC.

    Unit of measurement: `ppm`, `ppb`
    """

    VOLTAGE = "voltage"
    """Voltage.

    Unit of measurement: `V`, `mV`, `µV`, `kV`, `MV`
    """

    VOLUME = "volume"
    """Generic volume.

    Unit of measurement: `VOLUME_*` units
    - SI / metric: `mL`, `L`, `m³`
    - USCS / imperial: `ft³`, `CCF`, `fl. oz.`, `gal` (warning: volumes expressed in
    USCS/imperial units are currently assumed to be US volumes)
    """

    VOLUME_STORAGE = "volume_storage"
    """Generic stored volume.

    Use this device class for sensors measuring stored volume, for example the amount
    of fuel in a fuel tank.

    Unit of measurement: `VOLUME_*` units
    - SI / metric: `mL`, `L`, `m³`
    - USCS / imperial: `ft³`, `CCF`, `fl. oz.`, `gal` (warning: volumes expressed in
    USCS/imperial units are currently assumed to be US volumes)
    """

    VOLUME_FLOW_RATE = "volume_flow_rate"
    """Generic flow rate

    Unit of measurement: UnitOfVolumeFlowRate
    - SI / metric: `m³/h`, `L/min`, `mL/s`
    - USCS / imperial: `ft³/min`, `gal/min`
    """

    WATER = "water"
    """Water.

    Unit of measurement:
    - SI / metric: `m³`, `L`
    - USCS / imperial: `ft³`, `CCF`, `gal` (warning: volumes expressed in
    USCS/imperial units are currently assumed to be US volumes)
    """

    WEIGHT = "weight"
    """Generic weight, represents a measurement of an object's mass.

    Weight is used instead of mass to fit with every day language.

    Unit of measurement: `MASS_*` units
    - SI / metric: `µg`, `mg`, `g`, `kg`
    - USCS / imperial: `oz`, `lb`
    """

    WIND_DIRECTION = "wind_direction"
    """Wind direction.

    Unit of measurement: `°`
    """

    WIND_SPEED = "wind_speed"
    """Wind speed.

    Unit of measurement: `SPEED_*` units
    - SI /metric: `m/s`, `km/h`
    - USCS / imperial: `ft/s`, `mph`
    - Nautical: `kn`
    - Beaufort: `Beaufort`
    """


NON_NUMERIC_DEVICE_CLASSES = {
    SensorDeviceClass.DATE,
    SensorDeviceClass.ENUM,
    SensorDeviceClass.TIMESTAMP,
}

DEVICE_CLASSES_SCHEMA: Final = vol.All(vol.Lower, vol.Coerce(SensorDeviceClass))

# DEVICE_CLASSES is deprecated as of 2021.12
# use the SensorDeviceClass enum instead.
DEVICE_CLASSES: Final[list[str]] = [cls.value for cls in SensorDeviceClass]


class SensorStateClass(StrEnum):
    """State class for sensors."""

    MEASUREMENT = "measurement"
    """The state represents a measurement in present time."""

    MEASUREMENT_ANGLE = "measurement_angle"
    """The state represents a angle measurement in present time. Currently only degrees are supported."""

    TOTAL = "total"
    """The state represents a total amount.

    For example: net energy consumption"""

    TOTAL_INCREASING = "total_increasing"
    """The state represents a monotonically increasing total.

    For example: an amount of consumed gas"""


STATE_CLASSES_SCHEMA: Final = vol.All(vol.Lower, vol.Coerce(SensorStateClass))


STATE_CLASSES: Final[list[str]] = [cls.value for cls in SensorStateClass]

UNIT_CONVERTERS: dict[SensorDeviceClass | str | None, type[BaseUnitConverter]] = {
    SensorDeviceClass.AREA: AreaConverter,
    SensorDeviceClass.ATMOSPHERIC_PRESSURE: PressureConverter,
    SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION: BloodGlucoseConcentrationConverter,
    SensorDeviceClass.CONDUCTIVITY: ConductivityConverter,
    SensorDeviceClass.CURRENT: ElectricCurrentConverter,
    SensorDeviceClass.DATA_RATE: DataRateConverter,
    SensorDeviceClass.DATA_SIZE: InformationConverter,
    SensorDeviceClass.DISTANCE: DistanceConverter,
    SensorDeviceClass.DURATION: DurationConverter,
    SensorDeviceClass.ENERGY: EnergyConverter,
    SensorDeviceClass.ENERGY_DISTANCE: EnergyDistanceConverter,
    SensorDeviceClass.ENERGY_STORAGE: EnergyConverter,
    SensorDeviceClass.GAS: VolumeConverter,
    SensorDeviceClass.POWER: PowerConverter,
    SensorDeviceClass.POWER_FACTOR: UnitlessRatioConverter,
    SensorDeviceClass.PRECIPITATION: DistanceConverter,
    SensorDeviceClass.PRECIPITATION_INTENSITY: SpeedConverter,
    SensorDeviceClass.PRESSURE: PressureConverter,
    SensorDeviceClass.SPEED: SpeedConverter,
    SensorDeviceClass.TEMPERATURE: TemperatureConverter,
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS: UnitlessRatioConverter,
    SensorDeviceClass.VOLTAGE: ElectricPotentialConverter,
    SensorDeviceClass.VOLUME: VolumeConverter,
    SensorDeviceClass.VOLUME_STORAGE: VolumeConverter,
    SensorDeviceClass.VOLUME_FLOW_RATE: VolumeFlowRateConverter,
    SensorDeviceClass.WATER: VolumeConverter,
    SensorDeviceClass.WEIGHT: MassConverter,
    SensorDeviceClass.WIND_SPEED: SpeedConverter,
}

DEVICE_CLASS_UNITS: dict[SensorDeviceClass, set[type[StrEnum] | str | None]] = {
    SensorDeviceClass.APPARENT_POWER: set(UnitOfApparentPower),
    SensorDeviceClass.AQI: {None},
    SensorDeviceClass.AREA: set(UnitOfArea),
    SensorDeviceClass.ATMOSPHERIC_PRESSURE: set(UnitOfPressure),
    SensorDeviceClass.BATTERY: {PERCENTAGE},
    SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION: set(UnitOfBloodGlucoseConcentration),
    SensorDeviceClass.CO: {CONCENTRATION_PARTS_PER_MILLION},
    SensorDeviceClass.CO2: {CONCENTRATION_PARTS_PER_MILLION},
    SensorDeviceClass.CONDUCTIVITY: set(UnitOfConductivity),
    SensorDeviceClass.CURRENT: set(UnitOfElectricCurrent),
    SensorDeviceClass.DATA_RATE: set(UnitOfDataRate),
    SensorDeviceClass.DATA_SIZE: set(UnitOfInformation),
    SensorDeviceClass.DISTANCE: set(UnitOfLength),
    SensorDeviceClass.DURATION: {
        UnitOfTime.DAYS,
        UnitOfTime.HOURS,
        UnitOfTime.MINUTES,
        UnitOfTime.SECONDS,
        UnitOfTime.MILLISECONDS,
        UnitOfTime.MICROSECONDS,
    },
    SensorDeviceClass.ENERGY: set(UnitOfEnergy),
    SensorDeviceClass.ENERGY_DISTANCE: set(UnitOfEnergyDistance),
    SensorDeviceClass.ENERGY_STORAGE: set(UnitOfEnergy),
    SensorDeviceClass.FREQUENCY: set(UnitOfFrequency),
    SensorDeviceClass.GAS: {
        UnitOfVolume.CENTUM_CUBIC_FEET,
        UnitOfVolume.CUBIC_FEET,
        UnitOfVolume.CUBIC_METERS,
        UnitOfVolume.LITERS,
    },
    SensorDeviceClass.HUMIDITY: {PERCENTAGE},
    SensorDeviceClass.ILLUMINANCE: {LIGHT_LUX},
    SensorDeviceClass.IRRADIANCE: set(UnitOfIrradiance),
    SensorDeviceClass.MOISTURE: {PERCENTAGE},
    SensorDeviceClass.NITROGEN_DIOXIDE: {CONCENTRATION_MICROGRAMS_PER_CUBIC_METER},
    SensorDeviceClass.NITROGEN_MONOXIDE: {CONCENTRATION_MICROGRAMS_PER_CUBIC_METER},
    SensorDeviceClass.NITROUS_OXIDE: {CONCENTRATION_MICROGRAMS_PER_CUBIC_METER},
    SensorDeviceClass.OZONE: {CONCENTRATION_MICROGRAMS_PER_CUBIC_METER},
    SensorDeviceClass.PH: {None},
    SensorDeviceClass.PM1: {CONCENTRATION_MICROGRAMS_PER_CUBIC_METER},
    SensorDeviceClass.PM10: {CONCENTRATION_MICROGRAMS_PER_CUBIC_METER},
    SensorDeviceClass.PM25: {CONCENTRATION_MICROGRAMS_PER_CUBIC_METER},
    SensorDeviceClass.POWER_FACTOR: {PERCENTAGE, None},
    SensorDeviceClass.POWER: {
        UnitOfPower.MILLIWATT,
        UnitOfPower.WATT,
        UnitOfPower.KILO_WATT,
        UnitOfPower.MEGA_WATT,
        UnitOfPower.GIGA_WATT,
        UnitOfPower.TERA_WATT,
    },
    SensorDeviceClass.PRECIPITATION: set(UnitOfPrecipitationDepth),
    SensorDeviceClass.PRECIPITATION_INTENSITY: set(UnitOfVolumetricFlux),
    SensorDeviceClass.PRESSURE: set(UnitOfPressure),
    SensorDeviceClass.REACTIVE_POWER: set(UnitOfReactivePower),
    SensorDeviceClass.SIGNAL_STRENGTH: {
        SIGNAL_STRENGTH_DECIBELS,
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    },
    SensorDeviceClass.SOUND_PRESSURE: set(UnitOfSoundPressure),
    SensorDeviceClass.SPEED: {*UnitOfSpeed, *UnitOfVolumetricFlux},
    SensorDeviceClass.SULPHUR_DIOXIDE: {CONCENTRATION_MICROGRAMS_PER_CUBIC_METER},
    SensorDeviceClass.TEMPERATURE: set(UnitOfTemperature),
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS: {
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    },
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS: {
        CONCENTRATION_PARTS_PER_BILLION,
        CONCENTRATION_PARTS_PER_MILLION,
    },
    SensorDeviceClass.VOLTAGE: set(UnitOfElectricPotential),
    SensorDeviceClass.VOLUME: set(UnitOfVolume),
    SensorDeviceClass.VOLUME_FLOW_RATE: set(UnitOfVolumeFlowRate),
    SensorDeviceClass.VOLUME_STORAGE: set(UnitOfVolume),
    SensorDeviceClass.WATER: {
        UnitOfVolume.CENTUM_CUBIC_FEET,
        UnitOfVolume.CUBIC_FEET,
        UnitOfVolume.CUBIC_METERS,
        UnitOfVolume.GALLONS,
        UnitOfVolume.LITERS,
    },
    SensorDeviceClass.WEIGHT: set(UnitOfMass),
    SensorDeviceClass.WIND_DIRECTION: {DEGREE},
    SensorDeviceClass.WIND_SPEED: set(UnitOfSpeed),
}

UNITS_PRECISION = {
    UnitOfPressure.PA: 0,
    UnitOfEnergy.WATT_HOUR: 1,
}

DEVICE_CLASS_STATE_CLASSES: dict[SensorDeviceClass, set[SensorStateClass]] = {
    SensorDeviceClass.APPARENT_POWER: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.AQI: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.AREA: set(SensorStateClass),
    SensorDeviceClass.ATMOSPHERIC_PRESSURE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.BATTERY: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.CO: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.CO2: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.CONDUCTIVITY: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.CURRENT: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.DATA_RATE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.DATA_SIZE: set(SensorStateClass),
    SensorDeviceClass.DATE: set(),
    SensorDeviceClass.DISTANCE: set(SensorStateClass),
    SensorDeviceClass.DURATION: set(SensorStateClass),
    SensorDeviceClass.ENERGY: {
        SensorStateClass.TOTAL,
        SensorStateClass.TOTAL_INCREASING,
    },
    SensorDeviceClass.ENERGY_DISTANCE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.ENERGY_STORAGE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.ENUM: set(),
    SensorDeviceClass.FREQUENCY: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.GAS: {SensorStateClass.TOTAL, SensorStateClass.TOTAL_INCREASING},
    SensorDeviceClass.HUMIDITY: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.ILLUMINANCE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.IRRADIANCE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.MOISTURE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.MONETARY: {SensorStateClass.TOTAL},
    SensorDeviceClass.NITROGEN_DIOXIDE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.NITROGEN_MONOXIDE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.NITROUS_OXIDE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.OZONE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.PH: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.PM1: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.PM10: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.PM25: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.POWER_FACTOR: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.POWER: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.PRECIPITATION: set(SensorStateClass),
    SensorDeviceClass.PRECIPITATION_INTENSITY: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.PRESSURE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.REACTIVE_POWER: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.SIGNAL_STRENGTH: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.SOUND_PRESSURE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.SPEED: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.SULPHUR_DIOXIDE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.TEMPERATURE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.TIMESTAMP: set(),
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.VOLTAGE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.VOLUME: {
        SensorStateClass.TOTAL,
        SensorStateClass.TOTAL_INCREASING,
    },
    SensorDeviceClass.VOLUME_STORAGE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.VOLUME_FLOW_RATE: {SensorStateClass.MEASUREMENT},
    SensorDeviceClass.WATER: {
        SensorStateClass.TOTAL,
        SensorStateClass.TOTAL_INCREASING,
    },
    SensorDeviceClass.WEIGHT: {
        SensorStateClass.MEASUREMENT,
        SensorStateClass.TOTAL,
        SensorStateClass.TOTAL_INCREASING,
    },
    SensorDeviceClass.WIND_DIRECTION: {SensorStateClass.MEASUREMENT_ANGLE},
    SensorDeviceClass.WIND_SPEED: {SensorStateClass.MEASUREMENT},
}


STATE_CLASS_UNITS: dict[SensorStateClass | str, set[type[StrEnum] | str | None]] = {
    SensorStateClass.MEASUREMENT_ANGLE: {DEGREE},
}
