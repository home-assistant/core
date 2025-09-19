"""Constants for the Rejseplanen integration."""

from enum import IntEnum

DOMAIN = "rejseplanen"

CONF_AUTHENTICATION = "authentication"
CONF_STOP_ID = "stop_id"
CONF_ROUTE = "route"
CONF_DIRECTION = "direction"
CONF_DEPARTURE_TYPE = "departure_type"
CONF_NAME = "name"

DEFAULT_NAME = "Next departure"
DEFAULT_STOP_NAME = "Unknown stop"

BUS_TYPES = ["BUS", "EXB", "TB"]
TRAIN_TYPES = ["LET", "S", "REG", "IC", "LYN", "TOG"]
METRO_TYPES = ["M"]

ATTR_STOP_ID = "stop_id"
ATTR_STOP_NAME = "stop"
ATTR_ROUTE = "route"
ATTR_TYPE = "type"
ATTR_DIRECTION = "direction"
ATTR_FINAL_STOP = "final_stop"
ATTR_DUE_IN = "due_in"
ATTR_DUE_AT = "due_at"
ATTR_SCHEDULED_AT = "scheduled_at"
ATTR_REAL_TIME_AT = "real_time_at"
ATTR_TRACK = "track"
ATTR_NEXT_UP = "next_departures"

SCAN_INTERVAL_MINUTES = 5


class TransportClass(IntEnum):
    """Transport class numbers from Rejseplanen XML."""

    IC = 1  # InterCity trains
    ICL = 2  # InterCity Lyn trains
    RE = 4  # Regional trains
    TOG = 8  # Long distance trains
    S_TOG = 16  # S-trains (Copenhagen suburban)
    BUS = 32  # Regular city buses
    EXPRESS_BUS = 64  # Express/long-distance buses (S-bus/E-bus)
    NIGHT_BUS = 128  # Night buses (N-bus)
    FLEXIBLE_BUS = 256  # Flexible transport (Divbus)
    FERRY = 512  # Ferry
    METRO = 1024  # Metro
    LETBANE = 2048  # Light rail
    FLIGHT = 4096  # Flight


# Mapping from XML catOut values to transport classes
CATOUT_TO_CLASS = {
    # IC Group (cls=1)
    "IC": TransportClass.IC,
    "IB": TransportClass.IC,
    # ICL Group (cls=2)
    "ICL": TransportClass.ICL,
    "ICL-X": TransportClass.ICL,
    "IL": TransportClass.ICL,  # ICL+
    # Regional trains (cls=4)
    "Re": TransportClass.RE,
    "RA": TransportClass.RE,
    "RX": TransportClass.RE,
    # Long distance trains (cls=8)
    "EC": TransportClass.TOG,
    "IR": TransportClass.TOG,
    "IP": TransportClass.TOG,
    "ICE": TransportClass.TOG,
    "SJ": TransportClass.TOG,
    "EN": TransportClass.TOG,
    "ICN": TransportClass.TOG,
    "Pågatog": TransportClass.TOG,
    "NAT": TransportClass.TOG,  # Night trains
    "L": TransportClass.TOG,  # Local trains
    "SKOLE": TransportClass.TOG,
    "MTOG": TransportClass.TOG,
    "E-Tog": TransportClass.TOG,
    "R-netTog": TransportClass.TOG,
    # S-trains (cls=16)
    "S-Tog": TransportClass.S_TOG,
    # Regular buses (cls=32)
    "Bus": TransportClass.BUS,
    "Bybus": TransportClass.BUS,
    "E-Bus": TransportClass.BUS,
    "ServiceB": TransportClass.BUS,
    "R-net": TransportClass.BUS,
    "C-Bus": TransportClass.BUS,
    "TraktBus": TransportClass.BUS,
    "Taxa": TransportClass.BUS,
    # Express buses (cls=64)
    "X Bus": TransportClass.EXPRESS_BUS,
    "Ekspresb": TransportClass.EXPRESS_BUS,
    "Fjernbus": TransportClass.EXPRESS_BUS,
    # Night and special buses (cls=128)
    "Natbus": TransportClass.NIGHT_BUS,
    "Havnebus": TransportClass.NIGHT_BUS,
    "Flybus": TransportClass.NIGHT_BUS,
    "Sightseeing bus": TransportClass.NIGHT_BUS,
    "HV-bus": TransportClass.NIGHT_BUS,
    "Si-bus": TransportClass.NIGHT_BUS,
    # Flexible transport (cls=256)
    "Flexbus": TransportClass.FLEXIBLE_BUS,
    "Flextur": TransportClass.FLEXIBLE_BUS,
    "TELEBUS": TransportClass.FLEXIBLE_BUS,
    "Nærbus": TransportClass.FLEXIBLE_BUS,
    # Ferry (cls=512)
    "Færge": TransportClass.FERRY,
    "HF": TransportClass.FERRY,  # Fast ferry
    # Metro (cls=1024)
    "MET": TransportClass.METRO,
    # Light rail (cls=2048)
    "Letbane": TransportClass.LETBANE,
    "LTBUS": TransportClass.LETBANE,
    # Flight (cls=4096)
    "Fly": TransportClass.FLIGHT,
}

# User-friendly names for config flow - use string keys for cv.multi_select
DEPARTURE_TYPE_OPTIONS = {
    "ic": "InterCity trains (IC, IB)",
    "icl": "InterCity Lyn trains (ICL, ICL-X, ICL+)",
    "re": "Regional trains (Re, RA, RX)",
    "tog": "Long distance trains (EC, IR, ICE, SJ, etc.)",
    "s_tog": "S-trains (Copenhagen suburban)",
    "bus": "City buses",
    "express_bus": "Express buses",
    "night_bus": "Night & special buses",
    "flexible_bus": "Flexible transport",
    "ferry": "Ferry",
    "metro": "Metro",
    "letbane": "Light rail",
    "flight": "Flight",
}

# Mapping from string keys to TransportClass enum values
DEPARTURE_TYPE_TO_CLASS = {
    "ic": TransportClass.IC,
    "icl": TransportClass.ICL,
    "re": TransportClass.RE,
    "tog": TransportClass.TOG,
    "s_tog": TransportClass.S_TOG,
    "bus": TransportClass.BUS,
    "express_bus": TransportClass.EXPRESS_BUS,
    "night_bus": TransportClass.NIGHT_BUS,
    "flexible_bus": TransportClass.FLEXIBLE_BUS,
    "ferry": TransportClass.FERRY,
    "metro": TransportClass.METRO,
    "letbane": TransportClass.LETBANE,
    "flight": TransportClass.FLIGHT,
}
