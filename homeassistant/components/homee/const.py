"""Constants for the homee integration."""

# General
DOMAIN = "homee"

# Sensor mappings
OPEN_CLOSE_MAP = {
    0.0: "open",
    1.0: "closed",
    2.0: "partial",
    3.0: "opening",
    4.0: "closing",
}
OPEN_CLOSE_MAP_REVERSED = {
    0.0: "closed",
    1.0: "open",
    2.0: "partial",
    3.0: "cosing",
    4.0: "opening",
}
