"""Constants for the Airios integration."""

from enum import IntEnum, auto

from pyairios import ProductId


class BridgeType(IntEnum):
    """Type of RF bridge."""

    SERIAL = auto()
    NETWORK = auto()


DOMAIN = "airios"
DEFAULT_NAME = "Airios"
DEFAULT_SCAN_INTERVAL = 30

CONF_BRIDGE_RF_ADDRESS = "bridge_rf_address"
CONF_RF_ADDRESS = "rf_address"
CONF_DEFAULT_TYPE = BridgeType.SERIAL
CONF_DEFAULT_HOST = "192.168.1.254"
CONF_DEFAULT_PORT = 502
CONF_DEFAULT_SERIAL_SLAVE_ID = 207
CONF_DEFAULT_NETWORK_SLAVE_ID = 1


SUPPORTED_UNITS: dict[str, ProductId] = {
    "Siber DF Optima 2": ProductId.VMD_02RPS78,
    "Siber DF EVO": ProductId.VMD_02RPS78,
}

SUPPORTED_ACCESSORIES: dict[str, ProductId] = {
    "Siber 4 button remote": ProductId.VMN_05LM02,
}
