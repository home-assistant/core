"""Provides diagnostics for ZHA."""

from __future__ import annotations

import dataclasses
from importlib.metadata import version
from typing import Any

from zha.application.const import (
    ATTR_ATTRIBUTE,
    ATTR_DEVICE_TYPE,
    ATTR_IEEE,
    ATTR_IN_CLUSTERS,
    ATTR_OUT_CLUSTERS,
    ATTR_PROFILE_ID,
    ATTR_VALUE,
    UNKNOWN,
)
from zha.application.gateway import Gateway
from zha.zigbee.device import Device
from zigpy.config import CONF_NWK_EXTENDED_PAN_ID
from zigpy.profiles import PROFILES
from zigpy.types import Channels
from zigpy.zcl import Cluster

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_ALARM_MASTER_CODE
from .helpers import (
    ZHADeviceProxy,
    async_get_zha_device_proxy,
    get_zha_data,
    get_zha_gateway,
)

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

BELLOWS_VERSION = version("bellows")
ZIGPY_VERSION = version("zigpy")
ZIGPY_DECONZ_VERSION = version("zigpy-deconz")
ZIGPY_XBEE_VERSION = version("zigpy-xbee")
ZIGPY_ZNP_VERSION = version("zigpy-znp")
ZIGPY_ZIGATE_VERSION = version("zigpy-zigate")
ZHA_QUIRKS_VERSION = version("zha-quirks")
ZHA_VERSION = version("zha")


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
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    zha_data = get_zha_data(hass)
    gateway: Gateway = get_zha_gateway(hass)
    app = gateway.application_controller

    energy_scan = await app.energy_scan(
        channels=Channels.ALL_CHANNELS, duration_exp=4, count=1
    )

    return async_redact_data(
        {
            "config": zha_data.yaml_config,
            "config_entry": config_entry.as_dict(),
            "application_state": shallow_asdict(app.state),
            "energy_scan": {
                channel: 100 * energy / 255 for channel, energy in energy_scan.items()
            },
            "versions": {
                "bellows": BELLOWS_VERSION,
                "zigpy": ZIGPY_VERSION,
                "zigpy_deconz": ZIGPY_DECONZ_VERSION,
                "zigpy_xbee": ZIGPY_XBEE_VERSION,
                "zigpy_znp": ZIGPY_ZNP_VERSION,
                "zigpy_zigate": ZIGPY_ZIGATE_VERSION,
                "zhaquirks": ZHA_QUIRKS_VERSION,
                "zha": ZHA_VERSION,
            },
            "devices": [
                {
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "logical_type": device.device_type,
                }
                for device in gateway.devices.values()
            ],
        },
        KEYS_TO_REDACT,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    zha_device_proxy: ZHADeviceProxy = async_get_zha_device_proxy(hass, device.id)
    device_info: dict[str, Any] = zha_device_proxy.zha_device_info
    device_info[CLUSTER_DETAILS] = get_endpoint_cluster_attr_data(
        zha_device_proxy.device
    )
    return async_redact_data(device_info, KEYS_TO_REDACT)


def get_endpoint_cluster_attr_data(zha_device: Device) -> dict:
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
                ATTR_ATTRIBUTE: repr(attr_def),
                ATTR_VALUE: cluster.get(attr_def.name),
            }
            for attr_id, attr_def in cluster.attributes.items()
        },
        UNSUPPORTED_ATTRIBUTES: sorted(
            cluster.unsupported_attributes, key=lambda v: (isinstance(v, str), v)
        ),
    }
