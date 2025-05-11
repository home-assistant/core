"""Constants for the KNX integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Final, TypedDict

from xknx.dpt.dpt_20 import HVACControllerMode
from xknx.telegram import Telegram

from homeassistant.components.climate import FAN_AUTO, FAN_OFF, HVACAction, HVACMode
from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import KNXModule

DOMAIN: Final = "knx"
KNX_MODULE_KEY: HassKey[KNXModule] = HassKey(DOMAIN)

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
TELEGRAM_LOG_DEFAULT: Final = 1000
TELEGRAM_LOG_MAX: Final = 25000  # ~10 MB or ~25 hours of reasonable bus load

##
# Secure constants
##
CONST_KNX_STORAGE_KEY: Final = "knx/"
CONF_KNX_KNXKEY_FILENAME: Final = "knxkeys_filename"
CONF_KNX_KNXKEY_PASSWORD: Final = "knxkeys_password"

CONF_KNX_SECURE_USER_ID: Final = "user_id"
CONF_KNX_SECURE_USER_PASSWORD: Final = "user_password"
CONF_KNX_SECURE_DEVICE_AUTHENTICATION: Final = "device_authentication"


CONF_CONTEXT_TIMEOUT: Final = "context_timeout"
CONF_IGNORE_INTERNAL_STATE: Final = "ignore_internal_state"
CONF_PAYLOAD_LENGTH: Final = "payload_length"
CONF_RESET_AFTER: Final = "reset_after"
CONF_RESPOND_TO_READ: Final = "respond_to_read"
CONF_STATE_ADDRESS: Final = "state_address"
CONF_SYNC_STATE: Final = "sync_state"

# original hass yaml config
DATA_HASS_CONFIG: Final = "knx_hass_config"

ATTR_COUNTER: Final = "counter"
ATTR_SOURCE: Final = "source"


type AsyncMessageCallbackType = Callable[[Telegram], Awaitable[None]]
type MessageCallbackType = Callable[[Telegram], None]

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
    tunnel_endpoint_ia: str | None  # tunnelling only - not required (use get())
    # KNX secure
    user_id: int | None  # not required
    user_password: str | None  # not required
    device_authentication: str | None  # not required
    knxkeys_filename: str  # not required
    knxkeys_password: str  # not required
    backbone_key: str | None  # not required
    sync_latency_tolerance: int | None  # not required
    # OptionsFlow only
    state_updater: bool  # default state updater: True -> expire 60; False -> init
    rate_limit: int
    #   Integration only (not forwarded to xknx)
    telegram_log_size: int  # not required


class ColorTempModes(Enum):
    """Color temperature modes for config validation."""

    # YAML uses Enum.name (with vol.Upper), UI uses Enum.value for lookup
    ABSOLUTE = "7.600"
    ABSOLUTE_FLOAT = "9"
    RELATIVE = "5.001"


class FanZeroMode(StrEnum):
    """Enum for setting the fan zero mode."""

    OFF = FAN_OFF
    AUTO = FAN_AUTO


SUPPORTED_PLATFORMS_YAML: Final = {
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
}

SUPPORTED_PLATFORMS_UI: Final = {
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SWITCH,
}

# Map KNX controller modes to HA modes. This list might not be complete.
CONTROLLER_MODES: Final = {
    # Map DPT 20.105 HVAC control modes
    HVACControllerMode.AUTO: HVACMode.AUTO,
    HVACControllerMode.HEAT: HVACMode.HEAT,
    HVACControllerMode.COOL: HVACMode.COOL,
    HVACControllerMode.OFF: HVACMode.OFF,
    HVACControllerMode.FAN_ONLY: HVACMode.FAN_ONLY,
    HVACControllerMode.DEHUMIDIFICATION: HVACMode.DRY,
}

CURRENT_HVAC_ACTIONS: Final = {
    HVACMode.HEAT: HVACAction.HEATING,
    HVACMode.COOL: HVACAction.COOLING,
    HVACMode.OFF: HVACAction.OFF,
    HVACMode.FAN_ONLY: HVACAction.FAN,
    HVACMode.DRY: HVACAction.DRYING,
}


class CoverConf:
    """Common config keys for cover."""

    TRAVELLING_TIME_DOWN: Final = "travelling_time_down"
    TRAVELLING_TIME_UP: Final = "travelling_time_up"
    INVERT_UPDOWN: Final = "invert_updown"
    INVERT_POSITION: Final = "invert_position"
    INVERT_ANGLE: Final = "invert_angle"
