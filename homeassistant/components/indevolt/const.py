"""Constants for the Indevolt integration."""

DOMAIN = "indevolt"

# Default configurations
DEFAULT_PORT = 8080

# Config entry fields
CONF_SERIAL_NUMBER = "serial_number"
CONF_GENERATION = "generation"

# API write/read keys for energy and value for outdoor/portable mode
ENERGY_MODE_READ_KEY = "7101"
ENERGY_MODE_WRITE_KEY = "47005"
PORTABLE_MODE = 0

# API write key and value for real-time control mode
REALTIME_ACTION_KEY = "47015"
REALTIME_ACTION_MODE = 4

# API key fields
SENSOR_KEYS = {
    1: [
        "606",
        "7101",
        "2101",
        "2108",
        "2107",
        "6000",
        "6001",
        "6002",
        "1501",
        "1502",
        "1664",
        "1665",
        "1666",
        "1667",
        "6105",
        "21028",
        "1505",
    ],
    2: [
        "606",
        "7101",
        "2101",
        "2108",
        "2107",
        "6000",
        "6001",
        "6002",
        "1501",
        "1502",
        "1664",
        "1665",
        "1666",
        "1667",
        "142",
        "667",
        "2104",
        "2105",
        "11034",
        "6004",
        "6005",
        "6006",
        "6007",
        "11016",
        "2600",
        "2612",
        "1632",
        "1600",
        "1633",
        "1601",
        "1634",
        "1602",
        "1635",
        "1603",
        "9008",
        "9032",
        "9051",
        "9070",
        "9165",
        "9218",
        "9000",
        "9016",
        "9035",
        "9054",
        "9149",
        "9202",
        "9012",
        "9030",
        "9049",
        "9068",
        "9163",
        "9216",
        "9004",
        "9020",
        "9039",
        "9058",
        "9153",
        "9206",
        "9013",
        "19173",
        "19174",
        "19175",
        "19176",
        "19177",
        "680",
        "2618",
        "7171",
        "11011",
        "11009",
        "11010",
        "6105",
        "1505",
    ],
}

# The map of Power Limits per device generation
POWER_LIMITS: dict[int, dict[str, int]] = {
    1: {"max_discharge_power": 800, "max_charge_power": 1200},
    2: {"max_discharge_power": 2400, "max_charge_power": 2400},
}
