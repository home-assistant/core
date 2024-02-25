"""Helper functions for LG Netcast TV."""
from functools import partial
from typing import TypedDict

import defusedxml.ElementTree as DET
from pylgnetcast import LgNetCastClient
from requests import RequestException

from homeassistant.core import HomeAssistant


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
    # We're using UDAP to retrieve this information, which requires a specific User-Agent
    client.HEADER = {**LgNetCastClient.HEADER, "User-Agent": "UDAP/2.0"}

    try:
        resp = await hass.async_add_executor_job(
            partial(client._send_to_tv, payload={"target": "rootservice.xml"}),  # pylint: disable=protected-access
            "data",
        )
    except RequestException as err:
        raise LGNetCastDetailDiscoveryError(
            f"Error in connecting to {client.url}"
        ) from err

    if resp.status_code != 200:
        raise LGNetCastDetailDiscoveryError(
            "Invalid response ({resp.status_code}) from: {resp.url}"
        )

    try:
        tree = DET.fromstring(resp.text.encode("utf-8"))
    except DET.ParseError as err:
        raise LGNetCastDetailDiscoveryError("Invalid XML") from err

    return {
        "uuid": tree.findtext("device/uuid"),
        "model_name": tree.findtext("device/modelName"),
        "friendly_name": tree.findtext("device/friendlyName"),
    }
