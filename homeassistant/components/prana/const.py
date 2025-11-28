"""Constants for Prana integration."""

DOMAIN = "prana"

CONF_CONFIG = "config"
CONF_MDNS = "mdns"
CONF_HOST = "host"


class PranaFanType:
    """Enumeration of Prana fan types."""

    EXTRACT = "extract"
    SUPPLY = "supply"
    BOUNDED = "bounded"


class PranaSwitchType:
    """Enumerates Prana switch types exposed by the device API."""

    BOUND = "bound"
    HEATER = "heater"
    NIGHT = "night"
    BOOST = "boost"
    AUTO = "auto"
    AUTO_PLUS = "auto_plus"
    WINTER = "winter"


class PranaSensorType:
    """Enumerates Prana sensor types."""

    INSIDE_TEMPERATURE = "inside_temperature"
    OUTSIDE_TEMPERATURE = "outside_temperature"
    INSIDE_TEMPERATURE_2 = "inside_temperature_2"
    OUTSIDE_TEMPERATURE_2 = "outside_temperature_2"
    HUMIDITY = "humidity"
    VOC = "voc"
    CO2 = "co2"
    AIR_PRESSURE = "air_pressure"


class PranaLightType:
    """Enumerates Prana light controls."""

    BRIGHTNESS = "brightness"
