"""Constants for the Jewish calendar integration."""

BINARY_SENSORS = {
    "issur_melacha_in_effect": ("Issur Melacha in Effect", "mdi:power-plug-off")
}

DATA_SENSORS = {
    "date": ("Date", "mdi:judaism"),
    "weekly_portion": ("Parshat Hashavua", "mdi:book-open-variant"),
    "holiday": ("Holiday", "mdi:calendar-star"),
    "omer_count": ("Day of the Omer", "mdi:counter"),
    "daf_yomi": ("Daf Yomi", "mdi:book-open-variant"),
}

TIME_SENSORS = {
    "first_light": ("Alot Hashachar", "mdi:weather-sunset-up"),
    "talit": ("Talit and Tefillin", "mdi:calendar-clock"),
    "gra_end_shma": ('Latest time for Shma Gr"a', "mdi:calendar-clock"),
    "mga_end_shma": ('Latest time for Shma MG"A', "mdi:calendar-clock"),
    "gra_end_tfila": ('Latest time for Tefilla Gr"a', "mdi:calendar-clock"),
    "mga_end_tfila": ('Latest time for Tefilla MG"A', "mdi:calendar-clock"),
    "big_mincha": ("Mincha Gedola", "mdi:calendar-clock"),
    "small_mincha": ("Mincha Ketana", "mdi:calendar-clock"),
    "plag_mincha": ("Plag Hamincha", "mdi:weather-sunset-down"),
    "sunset": ("Shkia", "mdi:weather-sunset"),
    "first_stars": ("T'set Hakochavim", "mdi:weather-night"),
    "upcoming_shabbat_candle_lighting": (
        "Upcoming Shabbat Candle Lighting",
        "mdi:candle",
    ),
    "upcoming_shabbat_havdalah": ("Upcoming Shabbat Havdalah", "mdi:weather-night"),
    "upcoming_candle_lighting": ("Upcoming Candle Lighting", "mdi:candle"),
    "upcoming_havdalah": ("Upcoming Havdalah", "mdi:weather-night"),
}

CONF_DIASPORA = "diaspora"
CONF_LANGUAGE = "language"
CONF_CANDLE_LIGHT_MINUTES = "candle_lighting_minutes_before_sunset"
CONF_HAVDALAH_OFFSET_MINUTES = "havdalah_minutes_after_sunset"

CANDLE_LIGHT_DEFAULT = 18
