"""Helpers for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
from __future__ import annotations

import binascii
import collections
from collections.abc import Callable, Iterator
import dataclasses
from dataclasses import dataclass
import enum
import logging
import re
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

import voluptuous as vol
import zigpy.exceptions
import zigpy.types
import zigpy.util
import zigpy.zcl
from zigpy.zcl.foundation import CommandSchema
import zigpy.zdo.types as zdo_types

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import CLUSTER_TYPE_IN, CLUSTER_TYPE_OUT, CUSTOM_CONFIGURATION, DATA_ZHA
from .registries import BINDABLE_CLUSTERS

if TYPE_CHECKING:
    from .cluster_handlers import ClusterHandler
    from .device import ZHADevice
    from .gateway import ZHAGateway

_ClusterHandlerT = TypeVar("_ClusterHandlerT", bound="ClusterHandler")
_T = TypeVar("_T")
_R = TypeVar("_R")
_P = ParamSpec("_P")
_LOGGER = logging.getLogger(__name__)


@dataclass
class BindingPair:
    """Information for binding."""

    source_cluster: zigpy.zcl.Cluster
    target_ieee: zigpy.types.EUI64
    target_ep_id: int

    @property
    def destination_address(self) -> zdo_types.MultiAddress:
        """Return a ZDO multi address instance."""
        return zdo_types.MultiAddress(
            addrmode=3, ieee=self.target_ieee, endpoint=self.target_ep_id
        )


async def safe_read(
    cluster, attributes, allow_cache=True, only_cache=False, manufacturer=None
):
    """Swallow all exceptions from network read.

    If we throw during initialization, setup fails. Rather have an entity that
    exists, but is in a maybe wrong state, than no entity. This method should
    probably only be used during initialization.
    """
    try:
        result, _ = await cluster.read_attributes(
            attributes,
            allow_cache=allow_cache,
            only_cache=only_cache,
            manufacturer=manufacturer,
        )
        return result
    except Exception:  # pylint: disable=broad-except
        return {}


async def get_matched_clusters(
    source_zha_device: ZHADevice, target_zha_device: ZHADevice
) -> list[BindingPair]:
    """Get matched input/output cluster pairs for 2 devices."""
    source_clusters = source_zha_device.async_get_std_clusters()
    target_clusters = target_zha_device.async_get_std_clusters()
    clusters_to_bind = []

    for endpoint_id in source_clusters:
        for cluster_id in source_clusters[endpoint_id][CLUSTER_TYPE_OUT]:
            if cluster_id not in BINDABLE_CLUSTERS:
                continue
            if target_zha_device.nwk == 0x0000:
                cluster_pair = BindingPair(
                    source_cluster=source_clusters[endpoint_id][CLUSTER_TYPE_OUT][
                        cluster_id
                    ],
                    target_ieee=target_zha_device.ieee,
                    target_ep_id=target_zha_device.device.application.get_endpoint_id(
                        cluster_id, is_server_cluster=True
                    ),
                )
                clusters_to_bind.append(cluster_pair)
                continue
            for t_endpoint_id in target_clusters:
                if cluster_id in target_clusters[t_endpoint_id][CLUSTER_TYPE_IN]:
                    cluster_pair = BindingPair(
                        source_cluster=source_clusters[endpoint_id][CLUSTER_TYPE_OUT][
                            cluster_id
                        ],
                        target_ieee=target_zha_device.ieee,
                        target_ep_id=t_endpoint_id,
                    )
                    clusters_to_bind.append(cluster_pair)
    return clusters_to_bind


def cluster_command_schema_to_vol_schema(schema: CommandSchema) -> vol.Schema:
    """Convert a cluster command schema to a voluptuous schema."""
    return vol.Schema(
        {
            vol.Optional(field.name)
            if field.optional
            else vol.Required(field.name): schema_type_to_vol(field.type)
            for field in schema.fields
        }
    )


def schema_type_to_vol(field_type: Any) -> Any:
    """Convert a schema type to a voluptuous type."""
    if issubclass(field_type, enum.Flag) and field_type.__members__:
        return cv.multi_select(
            [key.replace("_", " ") for key in field_type.__members__]
        )
    if issubclass(field_type, enum.Enum) and field_type.__members__:
        return vol.In([key.replace("_", " ") for key in field_type.__members__])
    if (
        issubclass(field_type, zigpy.types.FixedIntType)
        or issubclass(field_type, enum.Flag)
        or issubclass(field_type, enum.Enum)
    ):
        return vol.All(
            vol.Coerce(int), vol.Range(field_type.min_value, field_type.max_value)
        )
    return str


def convert_to_zcl_values(
    fields: dict[str, Any], schema: CommandSchema
) -> dict[str, Any]:
    """Convert user input to ZCL values."""
    converted_fields: dict[str, Any] = {}
    for field in schema.fields:
        if field.name not in fields:
            continue
        value = fields[field.name]
        if issubclass(field.type, enum.Flag) and isinstance(value, list):
            new_value = 0

            for flag in value:
                if isinstance(flag, str):
                    new_value |= field.type[flag.replace(" ", "_")]
                else:
                    new_value |= flag

            value = field.type(new_value)
        elif issubclass(field.type, enum.Enum):
            value = (
                field.type[value.replace(" ", "_")]
                if isinstance(value, str)
                else field.type(value)
            )
        else:
            value = field.type(value)
        _LOGGER.debug(
            "Converted ZCL schema field(%s) value from: %s to: %s",
            field.name,
            fields[field.name],
            value,
        )
        converted_fields[field.name] = value
    return converted_fields


@callback
def async_is_bindable_target(source_zha_device, target_zha_device):
    """Determine if target is bindable to source."""
    if target_zha_device.nwk == 0x0000:
        return True

    source_clusters = source_zha_device.async_get_std_clusters()
    target_clusters = target_zha_device.async_get_std_clusters()

    for endpoint_id in source_clusters:
        for t_endpoint_id in target_clusters:
            matches = set(
                source_clusters[endpoint_id][CLUSTER_TYPE_OUT].keys()
            ).intersection(target_clusters[t_endpoint_id][CLUSTER_TYPE_IN].keys())
            if any(bindable in BINDABLE_CLUSTERS for bindable in matches):
                return True
    return False


@callback
def async_get_zha_config_value(
    config_entry: ConfigEntry, section: str, config_key: str, default: _T
) -> _T:
    """Get the value for the specified configuration from the ZHA config entry."""
    return (
        config_entry.options.get(CUSTOM_CONFIGURATION, {})
        .get(section, {})
        .get(config_key, default)
    )


def async_cluster_exists(hass, cluster_id, skip_coordinator=True):
    """Determine if a device containing the specified in cluster is paired."""
    zha_gateway = get_zha_gateway(hass)
    zha_devices = zha_gateway.devices.values()
    for zha_device in zha_devices:
        if skip_coordinator and zha_device.is_coordinator:
            continue
        clusters_by_endpoint = zha_device.async_get_clusters()
        for clusters in clusters_by_endpoint.values():
            if (
                cluster_id in clusters[CLUSTER_TYPE_IN]
                or cluster_id in clusters[CLUSTER_TYPE_OUT]
            ):
                return True
    return False


@callback
def async_get_zha_device(hass: HomeAssistant, device_id: str) -> ZHADevice:
    """Get a ZHA device for the given device registry id."""
    device_registry = dr.async_get(hass)
    registry_device = device_registry.async_get(device_id)
    if not registry_device:
        _LOGGER.error("Device id `%s` not found in registry", device_id)
        raise KeyError(f"Device id `{device_id}` not found in registry.")
    zha_gateway = get_zha_gateway(hass)
    try:
        ieee_address = list(registry_device.identifiers)[0][1]
        ieee = zigpy.types.EUI64.convert(ieee_address)
    except (IndexError, ValueError) as ex:
        _LOGGER.error(
            "Unable to determine device IEEE for device with device id `%s`", device_id
        )
        raise KeyError(
            f"Unable to determine device IEEE for device with device id `{device_id}`."
        ) from ex
    return zha_gateway.devices[ieee]


def find_state_attributes(states: list[State], key: str) -> Iterator[Any]:
    """Find attributes with matching key from states."""
    for state in states:
        if (value := state.attributes.get(key)) is not None:
            yield value


def mean_int(*args):
    """Return the mean of the supplied values."""
    return int(sum(args) / len(args))


def mean_tuple(*args):
    """Return the mean values along the columns of the supplied values."""
    return tuple(sum(x) / len(x) for x in zip(*args))


def reduce_attribute(
    states: list[State],
    key: str,
    default: Any | None = None,
    reduce: Callable[..., Any] = mean_int,
) -> Any:
    """Find the first attribute matching key from states.

    If none are found, return default.
    """
    attrs = list(find_state_attributes(states, key))

    if not attrs:
        return default

    if len(attrs) == 1:
        return attrs[0]

    return reduce(*attrs)


class LogMixin:
    """Log helper."""

    def log(self, level, msg, *args, **kwargs):
        """Log with level."""
        raise NotImplementedError

    def debug(self, msg, *args, **kwargs):
        """Debug level log."""
        return self.log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        """Info level log."""
        return self.log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        """Warning method log."""
        return self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        """Error level log."""
        return self.log(logging.ERROR, msg, *args, **kwargs)


def convert_install_code(value: str) -> zigpy.types.KeyData:
    """Convert string to install code bytes and validate length."""

    try:
        code = binascii.unhexlify(value.replace("-", "").lower())
    except binascii.Error as exc:
        raise vol.Invalid(f"invalid hex string: {value}") from exc

    if len(code) != 18:  # 16 byte code + 2 crc bytes
        raise vol.Invalid("invalid length of the install code")

    link_key = zigpy.util.convert_install_code(code)
    if link_key is None:
        raise vol.Invalid("invalid install code")

    return link_key


QR_CODES = (
    # Consciot
    r"^([\da-fA-F]{16})\|([\da-fA-F]{36})$",
    # Enbrighten
    r"""
        ^Z:
        ([0-9a-fA-F]{16})  # IEEE address
        \$I:
        ([0-9a-fA-F]{36})  # install code
        $
    """,
    # Aqara
    r"""
        \$A:
        ([0-9a-fA-F]{16})  # IEEE address
        \$I:
        ([0-9a-fA-F]{36})  # install code
        $
    """,
    # Bosch
    r"""
        ^RB01SG
        [0-9a-fA-F]{34}
        ([0-9a-fA-F]{16}) # IEEE address
        DLK
        ([0-9a-fA-F]{36}|[0-9a-fA-F]{32}) # install code / link key
        $
    """,
)


def qr_to_install_code(qr_code: str) -> tuple[zigpy.types.EUI64, zigpy.types.KeyData]:
    """Try to parse the QR code.

    if successful, return a tuple of a EUI64 address and install code.
    """

    for code_pattern in QR_CODES:
        match = re.search(code_pattern, qr_code, re.VERBOSE)
        if match is None:
            continue

        ieee_hex = binascii.unhexlify(match[1])
        ieee = zigpy.types.EUI64(ieee_hex[::-1])

        # Bosch supplies (A) device specific link key (DSLK) or (A) install code + crc
        if "RB01SG" in code_pattern and len(match[2]) == 32:
            link_key_hex = binascii.unhexlify(match[2])
            link_key = zigpy.types.KeyData(link_key_hex)
            return ieee, link_key
        install_code = match[2]
        # install_code sanity check
        link_key = convert_install_code(install_code)
        return ieee, link_key

    raise vol.Invalid(f"couldn't convert qr code: {qr_code}")


@dataclasses.dataclass(kw_only=True, slots=True)
class ZHAData:
    """ZHA component data stored in `hass.data`."""

    yaml_config: ConfigType = dataclasses.field(default_factory=dict)
    platforms: collections.defaultdict[Platform, list] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(list)
    )
    gateway: ZHAGateway | None = dataclasses.field(default=None)
    device_trigger_cache: dict[str, tuple[str, dict]] = dataclasses.field(
        default_factory=dict
    )
    allow_polling: bool = dataclasses.field(default=False)


def get_zha_data(hass: HomeAssistant) -> ZHAData:
    """Get the global ZHA data object."""
    if DATA_ZHA not in hass.data:
        hass.data[DATA_ZHA] = ZHAData()

    return hass.data[DATA_ZHA]


def get_zha_gateway(hass: HomeAssistant) -> ZHAGateway:
    """Get the ZHA gateway object."""
    if (zha_gateway := get_zha_data(hass).gateway) is None:
        raise ValueError("No gateway object exists")

    return zha_gateway
