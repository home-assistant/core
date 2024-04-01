"""Constants for the KNX integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Final, TypedDict

from xknx.telegram import Telegram

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    HVACAction,
    HVACMode,
)
from homeassistant.const import Platform

DOMAIN: Final = "knx"

# Address is used for configuration and services by the same functions so the key has to match
KNX_ADDRESS: Final = "address"

CONF_INVERT: Final = "invert"
CONF_KNX_EXPOSE: Final = "expose"
CONF_KNX_INDIVIDUAL_ADDRESS: Final = "individual_address"

##
# Connection constants
##
CONF_KNX_CONNECTION_TYPE: Final = "connection_type"
CONF_KNX_AUTOMATIC: Final = "automatic"
CONF_KNX_ROUTING: Final = "routing"
CONF_KNX_ROUTING_BACKBONE_KEY: Final = "backbone_key"
CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: Final = "sync_latency_tolerance"
CONF_KNX_ROUTING_SECURE: Final = "routing_secure"
CONF_KNX_TUNNELING: Final = "tunneling"
CONF_KNX_TUNNELING_TCP: Final = "tunneling_tcp"
CONF_KNX_TUNNELING_TCP_SECURE: Final = "tunneling_tcp_secure"
CONF_KNX_LOCAL_IP: Final = "local_ip"
CONF_KNX_MCAST_GRP: Final = "multicast_group"
CONF_KNX_MCAST_PORT: Final = "multicast_port"
CONF_KNX_TUNNEL_ENDPOINT_IA: Final = "tunnel_endpoint_ia"

CONF_KNX_RATE_LIMIT: Final = "rate_limit"
CONF_KNX_ROUTE_BACK: Final = "route_back"
CONF_KNX_STATE_UPDATER: Final = "state_updater"
CONF_KNX_DEFAULT_STATE_UPDATER: Final = True
CONF_KNX_DEFAULT_RATE_LIMIT: Final = 0

DEFAULT_ROUTING_IA: Final = "0.0.240"

CONF_KNX_TELEGRAM_LOG_SIZE: Final = "telegram_log_size"
TELEGRAM_LOG_DEFAULT: Final = 200
TELEGRAM_LOG_MAX: Final = 5000  # ~2 MB or ~5 hours of reasonable bus load

##
# Secure constants
##
CONST_KNX_STORAGE_KEY: Final = "knx/"
CONF_KNX_KNXKEY_FILENAME: Final = "knxkeys_filename"
CONF_KNX_KNXKEY_PASSWORD: Final = "knxkeys_password"

CONF_KNX_SECURE_USER_ID: Final = "user_id"
CONF_KNX_SECURE_USER_PASSWORD: Final = "user_password"
CONF_KNX_SECURE_DEVICE_AUTHENTICATION: Final = "device_authentication"


CONF_PAYLOAD_LENGTH: Final = "payload_length"
CONF_RESET_AFTER: Final = "reset_after"
CONF_RESPOND_TO_READ: Final = "respond_to_read"
CONF_STATE_ADDRESS: Final = "state_address"
CONF_SYNC_STATE: Final = "sync_state"

# yaml config merged with config entry data
DATA_KNX_CONFIG: Final = "knx_config"
# original hass yaml config
DATA_HASS_CONFIG: Final = "knx_hass_config"

ATTR_COUNTER: Final = "counter"
ATTR_SOURCE: Final = "source"

# dispatcher signal for KNX interface device triggers
SIGNAL_KNX_TELEGRAM_DICT: Final = "knx_telegram_dict"

AsyncMessageCallbackType = Callable[[Telegram], Awaitable[None]]
MessageCallbackType = Callable[[Telegram], None]

SERVICE_KNX_SEND: Final = "send"
SERVICE_KNX_ATTR_PAYLOAD: Final = "payload"
SERVICE_KNX_ATTR_TYPE: Final = "type"
SERVICE_KNX_ATTR_RESPONSE: Final = "response"
SERVICE_KNX_ATTR_REMOVE: Final = "remove"
SERVICE_KNX_EVENT_REGISTER: Final = "event_register"
SERVICE_KNX_EXPOSURE_REGISTER: Final = "exposure_register"
SERVICE_KNX_READ: Final = "read"


class KNXConfigEntryData(TypedDict, total=False):
    """Config entry for the KNX integration."""

    connection_type: str
    individual_address: str
    local_ip: str | None  # not required
    multicast_group: str
    multicast_port: int
    route_back: bool  # not required
    host: str  # only required for tunnelling
    port: int  # only required for tunnelling
    tunnel_endpoint_ia: str | None
    # KNX secure
    user_id: int | None  # not required
    user_password: str | None  # not required
    device_authentication: str | None  # not required
    knxkeys_filename: str  # not required
    knxkeys_password: str  # not required
    backbone_key: str | None  # not required
    sync_latency_tolerance: int | None  # not required
    # OptionsFlow only
    state_updater: bool
    rate_limit: int
    #   Integration only (not forwarded to xknx)
    telegram_log_size: int  # not required


class ColorTempModes(Enum):
    """Color temperature modes for config validation."""

    ABSOLUTE = "DPT-7.600"
    ABSOLUTE_FLOAT = "DPT-9"
    RELATIVE = "DPT-5.001"


SUPPORTED_PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.DATE,
    Platform.DATETIME,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NOTIFY,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.TIME,
    Platform.WEATHER,
]

# Map KNX controller modes to HA modes. This list might not be complete.
CONTROLLER_MODES: Final = {
    # Map DPT 20.105 HVAC control modes
    "Auto": HVACMode.AUTO,
    "Heat": HVACMode.HEAT,
    "Cool": HVACMode.COOL,
    "Off": HVACMode.OFF,
    "Fan only": HVACMode.FAN_ONLY,
    "Dry": HVACMode.DRY,
}

CURRENT_HVAC_ACTIONS: Final = {
    HVACMode.HEAT: HVACAction.HEATING,
    HVACMode.COOL: HVACAction.COOLING,
    HVACMode.OFF: HVACAction.OFF,
    HVACMode.FAN_ONLY: HVACAction.FAN,
    HVACMode.DRY: HVACAction.DRYING,
}

PRESET_MODES: Final = {
    # Map DPT 20.102 HVAC operating modes to HA presets
    "Auto": PRESET_NONE,
    "Frost Protection": PRESET_ECO,
    "Night": PRESET_SLEEP,
    "Standby": PRESET_AWAY,
    "Comfort": PRESET_COMFORT,
}
