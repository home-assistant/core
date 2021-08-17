"""Constants for the Jewish calendar integration."""
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import DEVICE_CLASS_TIMESTAMP

DATA_SENSORS = (
    SensorEntityDescription(key="date", name="Date", icon="mdi:judaism"),
    SensorEntityDescription(
        key="weekly_portion", name="Parshat Hashavua", icon="mdi:book-open-variant"
    ),
    SensorEntityDescription(key="holiday", name="Holiday", icon="mdi:calendar-star"),
    SensorEntityDescription(
        key="omer_count", name="Day of the Omer", icon="mdi:counter"
    ),
    SensorEntityDescription(
        key="daf_yomi", name="Daf Yomi", icon="mdi:book-open-variant"
    ),
)

TIME_SENSORS = (
    SensorEntityDescription(
        key="first_light",
        name="Alot Hashachar",
        icon="mdi:weather-sunset-up",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="talit",
        name="Talit and Tefillin",
        icon="mdi:calendar-clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="gra_end_shma",
        name='Latest time for Shma Gr"a',
        icon="mdi:calendar-clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="mga_end_shma",
        name='Latest time for Shma MG"A',
        icon="mdi:calendar-clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="gra_end_tfila",
        name='Latest time for Tefilla Gr"a',
        icon="mdi:calendar-clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="mga_end_tfila",
        name='Latest time for Tefilla MG"A',
        icon="mdi:calendar-clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="big_mincha",
        name="Mincha Gedola",
        icon="mdi:calendar-clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="small_mincha",
        name="Mincha Ketana",
        icon="mdi:calendar-clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="plag_mincha",
        name="Plag Hamincha",
        icon="mdi:weather-sunset-down",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="sunset",
        name="Shkia",
        icon="mdi:weather-sunset",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="first_stars",
        name="T'set Hakochavim",
        icon="mdi:weather-night",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="upcoming_shabbat_candle_lighting",
        name="Upcoming Shabbat Candle Lighting",
        icon="mdi:candle",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="upcoming_shabbat_havdalah",
        name="Upcoming Shabbat Havdalah",
        icon="mdi:weather-night",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="upcoming_candle_lighting",
        name="Upcoming Candle Lighting",
        icon="mdi:candle",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="upcoming_havdalah",
        name="Upcoming Havdalah",
        icon="mdi:weather-night",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
)

CONF_DIASPORA = "diaspora"
CONF_LANGUAGE = "language"
CONF_CANDLE_LIGHT_MINUTES = "candle_lighting_minutes_before_sunset"
CONF_HAVDALAH_OFFSET_MINUTES = "havdalah_minutes_after_sunset"

CANDLE_LIGHT_DEFAULT = 18
