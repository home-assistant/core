"""Const for TP-Link."""

from __future__ import annotations

from typing import Final

from kasa.smart.modules.clean import AreaUnit

from homeassistant.const import Platform, UnitOfArea, UnitOfTemperature

DOMAIN = "tplink"

DISCOVERY_TIMEOUT = 5  # Home Assistant will complain if startup takes > 10s
CONNECT_TIMEOUT = 5

# Identifier used for primary control state.
PRIMARY_STATE_ID = "state"

ATTR_CURRENT_A: Final = "current_a"
ATTR_CURRENT_POWER_W: Final = "current_power_w"
ATTR_TODAY_ENERGY_KWH: Final = "today_energy_kwh"
ATTR_TOTAL_ENERGY_KWH: Final = "total_energy_kwh"

CONF_DEVICE_CONFIG: Final = "device_config"
CONF_CREDENTIALS_HASH: Final = "credentials_hash"
CONF_CONNECTION_PARAMETERS: Final = "connection_parameters"
CONF_USES_HTTP: Final = "uses_http"
CONF_AES_KEYS: Final = "aes_keys"
CONF_CAMERA_CREDENTIALS = "camera_credentials"
CONF_LIVE_VIEW = "live_view"

CONF_CONFIG_ENTRY_MINOR_VERSION: Final = 5

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VACUUM,
]

UNIT_MAPPING = {
    "celsius": UnitOfTemperature.CELSIUS,
    "fahrenheit": UnitOfTemperature.FAHRENHEIT,
    AreaUnit.Sqm: UnitOfArea.SQUARE_METERS,
    AreaUnit.Sqft: UnitOfArea.SQUARE_FEET,
}
