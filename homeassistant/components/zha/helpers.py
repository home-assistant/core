"""Helper functions for the ZHA integration."""

import enum
import logging
from typing import Any

import voluptuous as vol
from zha.application.const import CLUSTER_TYPE_IN, CLUSTER_TYPE_OUT, DATA_ZHA
from zha.application.gateway import ZHAGateway
from zha.application.helpers import ZHAData
import zigpy.exceptions
import zigpy.types
from zigpy.types import EUI64
import zigpy.util
import zigpy.zcl
from zigpy.zcl.foundation import CommandSchema

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr

from . import HAZHAData, ZHADeviceProxy, ZHAGatewayProxy

_LOGGER = logging.getLogger(__name__)


def get_zha_data(hass: HomeAssistant) -> HAZHAData:
    """Get the global ZHA data object."""
    if DATA_ZHA not in hass.data:
        hass.data[DATA_ZHA] = HAZHAData(data=ZHAData())

    return hass.data[DATA_ZHA]


def get_zha_gateway(hass: HomeAssistant) -> ZHAGateway:
    """Get the ZHA gateway object."""
    if (gateway_proxy := get_zha_data(hass).gateway_proxy) is None:
        raise ValueError("No gateway object exists")

    return gateway_proxy.gateway


def get_zha_gateway_proxy(hass: HomeAssistant) -> ZHAGatewayProxy:
    """Get the ZHA gateway object."""
    if (gateway_proxy := get_zha_data(hass).gateway_proxy) is None:
        raise ValueError("No gateway object exists")

    return gateway_proxy


@callback
def async_get_zha_device_proxy(hass: HomeAssistant, device_id: str) -> ZHADeviceProxy:
    """Get a ZHA device for the given device registry id."""
    device_registry = dr.async_get(hass)
    registry_device = device_registry.async_get(device_id)
    if not registry_device:
        _LOGGER.error("Device id `%s` not found in registry", device_id)
        raise KeyError(f"Device id `{device_id}` not found in registry.")
    zha_gateway_proxy = get_zha_gateway_proxy(hass)
    try:
        ieee_address = list(registry_device.identifiers)[0][1]
        ieee = EUI64.convert(ieee_address)
    except (IndexError, ValueError) as ex:
        _LOGGER.error(
            "Unable to determine device IEEE for device with device id `%s`", device_id
        )
        raise KeyError(
            f"Unable to determine device IEEE for device with device id `{device_id}`."
        ) from ex
    return zha_gateway_proxy.device_proxies[ieee]


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


def async_cluster_exists(hass: HomeAssistant, cluster_id, skip_coordinator=True):
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
