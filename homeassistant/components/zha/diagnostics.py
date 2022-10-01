"""Provides diagnostics for ZHA."""
from __future__ import annotations

import dataclasses
from typing import Any

import bellows
import pkg_resources
import zigpy
from zigpy.config import CONF_NWK_EXTENDED_PAN_ID
from zigpy.profiles import PROFILES
from zigpy.zcl import Cluster
import zigpy_deconz
import zigpy_xbee
import zigpy_zigate
import zigpy_znp

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .core.const import (
    ATTR_ATTRIBUTE_NAME,
    ATTR_DEVICE_TYPE,
    ATTR_IEEE,
    ATTR_IN_CLUSTERS,
    ATTR_OUT_CLUSTERS,
    ATTR_PROFILE_ID,
    ATTR_VALUE,
    CONF_ALARM_MASTER_CODE,
    DATA_ZHA,
    DATA_ZHA_CONFIG,
    DATA_ZHA_GATEWAY,
    UNKNOWN,
)
from .core.device import ZHADevice
from .core.gateway import ZHAGateway
from .core.helpers import async_get_zha_device

KEYS_TO_REDACT = {
    ATTR_IEEE,
    CONF_UNIQUE_ID,
    CONF_ALARM_MASTER_CODE,
    "network_key",
    CONF_NWK_EXTENDED_PAN_ID,
    "partner_ieee",
}

ATTRIBUTES = "attributes"
CLUSTER_DETAILS = "cluster_details"
UNSUPPORTED_ATTRIBUTES = "unsupported_attributes"


def shallow_asdict(obj: Any) -> dict:
    """Return a shallow copy of a dataclass as a dict."""
    if hasattr(obj, "__dataclass_fields__"):
        result = {}

        for field in dataclasses.fields(obj):
            result[field.name] = shallow_asdict(getattr(obj, field.name))

        return result
    if hasattr(obj, "as_dict"):
        return obj.as_dict()
    return obj


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    config: dict = hass.data[DATA_ZHA].get(DATA_ZHA_CONFIG, {})
    gateway: ZHAGateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    return async_redact_data(
        {
            "config": config,
            "config_entry": config_entry.as_dict(),
            "application_state": shallow_asdict(gateway.application_controller.state),
            "versions": {
                "bellows": bellows.__version__,
                "zigpy": zigpy.__version__,
                "zigpy_deconz": zigpy_deconz.__version__,
                "zigpy_xbee": zigpy_xbee.__version__,
                "zigpy_znp": zigpy_znp.__version__,
                "zigpy_zigate": zigpy_zigate.__version__,
                "zhaquirks": pkg_resources.get_distribution("zha-quirks").version,
            },
        },
        KEYS_TO_REDACT,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: dr.DeviceEntry
) -> dict:
    """Return diagnostics for a device."""
    zha_device: ZHADevice = async_get_zha_device(hass, device.id)
    device_info: dict[str, Any] = zha_device.zha_device_info
    device_info[CLUSTER_DETAILS] = get_endpoint_cluster_attr_data(zha_device)
    return async_redact_data(device_info, KEYS_TO_REDACT)


def get_endpoint_cluster_attr_data(zha_device: ZHADevice) -> dict:
    """Return endpoint cluster attribute data."""
    cluster_details = {}
    for ep_id, endpoint in zha_device.device.endpoints.items():
        if ep_id == 0:
            continue
        endpoint_key = (
            f"{PROFILES.get(endpoint.profile_id).DeviceType(endpoint.device_type).name}"
            if PROFILES.get(endpoint.profile_id) is not None
            and endpoint.device_type is not None
            else UNKNOWN
        )
        cluster_details[ep_id] = {
            ATTR_DEVICE_TYPE: {
                CONF_NAME: endpoint_key,
                CONF_ID: endpoint.device_type,
            },
            ATTR_PROFILE_ID: endpoint.profile_id,
            ATTR_IN_CLUSTERS: {
                f"0x{cluster_id:04x}": {
                    "endpoint_attribute": cluster.ep_attribute,
                    **get_cluster_attr_data(cluster),
                }
                for cluster_id, cluster in endpoint.in_clusters.items()
            },
            ATTR_OUT_CLUSTERS: {
                f"0x{cluster_id:04x}": {
                    "endpoint_attribute": cluster.ep_attribute,
                    **get_cluster_attr_data(cluster),
                }
                for cluster_id, cluster in endpoint.out_clusters.items()
            },
        }
    return cluster_details


def get_cluster_attr_data(cluster: Cluster) -> dict:
    """Return cluster attribute data."""
    return {
        ATTRIBUTES: {
            f"0x{attr_id:04x}": {
                ATTR_ATTRIBUTE_NAME: attr_def.name,
                ATTR_VALUE: attr_value,
            }
            for attr_id, attr_def in cluster.attributes.items()
            if (attr_value := cluster.get(attr_def.name)) is not None
        },
        UNSUPPORTED_ATTRIBUTES: {
            f"0x{cluster.find_attribute(u_attr).id:04x}": {
                ATTR_ATTRIBUTE_NAME: cluster.find_attribute(u_attr).name
            }
            for u_attr in cluster.unsupported_attributes
        },
    }
