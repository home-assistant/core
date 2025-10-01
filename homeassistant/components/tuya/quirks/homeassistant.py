"""Quirks registry."""

from __future__ import annotations

from enum import StrEnum


def parse_enum[T: StrEnum](enum_class: type[T], value: str | None) -> T | None:
    """Parse a string to an enum member, or return None if value is None."""
    if value is None:
        return None
    try:
        return enum_class(value)
    except ValueError:
        return None


class TuyaEntityCategory(StrEnum):
    """Category of an entity.

    An entity with a category will:
    - Not be exposed to cloud, Alexa, or Google Assistant components
    - Not be included in indirect service calls to devices or areas
    """

    # Config: An entity which allows changing the configuration of a device.
    CONFIG = "config"

    # Diagnostic: An entity exposing some configuration parameter,
    # or diagnostics of a device.
    DIAGNOSTIC = "diagnostic"


class TuyaCoverDeviceClass(StrEnum):
    """Device class for cover."""

    # Keep synchronized with homeassistant
    AWNING = "awning"
    BLIND = "blind"
    CURTAIN = "curtain"
    DAMPER = "damper"
    DOOR = "door"
    GARAGE = "garage"
    GATE = "gate"
    SHADE = "shade"
    SHUTTER = "shutter"
    WINDOW = "window"


class TuyaSensorDeviceClass(StrEnum):
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
    ABSOLUTE_HUMIDITY = "absolute_humidity"
    """Absolute humidity.

    Unit of measurement: `g/m³`, `mg/m³`
    """

    APPARENT_POWER = "apparent_power"
    """Apparent power.

    Unit of measurement: `mVA`, `VA`, `kVA`
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

    Unit of measurement: `S/cm`, `mS/cm`, `μS/cm`
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

    Unit of measurement: `d`, `h`, `min`, `s`, `ms`, `μs`
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

    Unit of measurement: `kWh/100km`, `Wh/km`, `mi/kWh`, `km/kWh`
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
    - USCS / imperial: `ft³`, `CCF`, `MCF`
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

    Unit of measurement: `μg/m³`
    """

    NITROGEN_MONOXIDE = "nitrogen_monoxide"
    """Amount of NO.

    Unit of measurement: `μg/m³`
    """

    NITROUS_OXIDE = "nitrous_oxide"
    """Amount of N2O.

    Unit of measurement: `μg/m³`
    """

    OZONE = "ozone"
    """Amount of O3.

    Unit of measurement: `μg/m³`
    """

    PH = "ph"
    """Potential hydrogen (acidity/alkalinity).

    Unit of measurement: Unitless
    """

    PM1 = "pm1"
    """Particulate matter <= 1 μm.

    Unit of measurement: `μg/m³`
    """

    PM10 = "pm10"
    """Particulate matter <= 10 μm.

    Unit of measurement: `μg/m³`
    """

    PM25 = "pm25"
    """Particulate matter <= 2.5 μm.

    Unit of measurement: `μg/m³`
    """

    PM4 = "pm4"
    """Particulate matter <= 4 μm.

    Unit of measurement: `μg/m³`
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
    - `inH₂O`
    """

    REACTIVE_ENERGY = "reactive_energy"
    """Reactive energy.

    Unit of measurement: `varh`, `kvarh`
    """

    REACTIVE_POWER = "reactive_power"
    """Reactive power.

    Unit of measurement: `mvar`, `var`, `kvar`
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

    Unit of measurement: `μg/m³`
    """

    TEMPERATURE = "temperature"
    """Temperature.

    Unit of measurement: `°C`, `°F`, `K`
    """

    VOLATILE_ORGANIC_COMPOUNDS = "volatile_organic_compounds"
    """Amount of VOC.

    Unit of measurement: `μg/m³`, `mg/m³`
    """

    VOLATILE_ORGANIC_COMPOUNDS_PARTS = "volatile_organic_compounds_parts"
    """Ratio of VOC.

    Unit of measurement: `ppm`, `ppb`
    """

    VOLTAGE = "voltage"
    """Voltage.

    Unit of measurement: `V`, `mV`, `μV`, `kV`, `MV`
    """

    VOLUME = "volume"
    """Generic volume.

    Unit of measurement: `VOLUME_*` units
    - SI / metric: `mL`, `L`, `m³`
    - USCS / imperial: `ft³`, `CCF`, `MCF`, `fl. oz.`, `gal` (warning: volumes expressed in
    USCS/imperial units are currently assumed to be US volumes)
    """

    VOLUME_STORAGE = "volume_storage"
    """Generic stored volume.

    Use this device class for sensors measuring stored volume, for example the amount
    of fuel in a fuel tank.

    Unit of measurement: `VOLUME_*` units
    - SI / metric: `mL`, `L`, `m³`
    - USCS / imperial: `ft³`, `CCF`, `MCF`, `fl. oz.`, `gal` (warning: volumes expressed in
    USCS/imperial units are currently assumed to be US volumes)
    """

    VOLUME_FLOW_RATE = "volume_flow_rate"
    """Generic flow rate

    Unit of measurement: UnitOfVolumeFlowRate
    - SI / metric: `m³/h`, `m³/min`, `m³/s`, `L/h`, `L/min`, `L/s`, `mL/s`
    - USCS / imperial: `ft³/min`, `gal/min`
    """

    WATER = "water"
    """Water.

    Unit of measurement:
    - SI / metric: `m³`, `L`
    - USCS / imperial: `ft³`, `CCF`, `MCF`, `gal` (warning: volumes expressed in
    USCS/imperial units are currently assumed to be US volumes)
    """

    WEIGHT = "weight"
    """Generic weight, represents a measurement of an object's mass.

    Weight is used instead of mass to fit with every day language.

    Unit of measurement: `MASS_*` units
    - SI / metric: `μg`, `mg`, `g`, `kg`
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
