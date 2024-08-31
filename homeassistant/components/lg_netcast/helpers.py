"""Helper functions for LG Netcast TV."""

from typing import TypedDict
import xml.etree.ElementTree as ET

from pylgnetcast import LgNetCastClient
from requests import RequestException

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN


class LGNetCastDetailDiscoveryError(Exception):
    """Unable to retrieve details from Netcast TV."""


class NetcastDetails(TypedDict):
    """Netcast TV Details."""

    uuid: str
    model_name: str
    friendly_name: str


async def async_discover_netcast_details(
    hass: HomeAssistant, client: LgNetCastClient
) -> NetcastDetails:
    """Discover UUID and Model Name from Netcast Tv."""
    try:
        resp = await hass.async_add_executor_job(client.query_device_info)
    except RequestException as err:
        raise LGNetCastDetailDiscoveryError(
            f"Error in connecting to {client.url}"
        ) from err
    except ET.ParseError as err:
        raise LGNetCastDetailDiscoveryError("Invalid XML") from err

    if resp is None:
        raise LGNetCastDetailDiscoveryError("Empty response received")

    return resp


@callback
def async_get_device_entry_by_device_id(
    hass: HomeAssistant, device_id: str
) -> DeviceEntry:
    """Get Device Entry from Device Registry by device ID.

    Raises ValueError if device ID is invalid.
    """
    device_reg = dr.async_get(hass)
    if (device := device_reg.async_get(device_id)) is None:
        raise ValueError(f"Device {device_id} is not a valid {DOMAIN} device.")

    return device
