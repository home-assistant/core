"""This file is used as a hub for imports."""

import defusedxml.ElementTree as defused_ET

from ..client import PapouchApiClient
from .base import PapouchDevice
from .quido import Quido
from .th2e import TH2E


async def create_device(api_client: PapouchApiClient) -> PapouchDevice | None:
    """Function that creates proper device instance.

    Returns "None" if the device is not supported
    or when the device doesn't have proper identification tag.
    """

    info = await api_client.fetch_info()

    try:
        root = defused_ET.fromstring(info)
        heartbeat = root.find("heartbeat")

        if heartbeat is None:
            return None

        device = heartbeat.attrib.get("device")

    except defused_ET.ParseError:
        return None
    except AttributeError:
        return None

    if "Quido" in device:
        # settings are being fetched now, because ctor isn't async
        settings = await api_client.fetch_settings()
        return Quido(api_client, settings, info)
    elif "TH2E" in device:
        return TH2E(api_client, info)
    else:
        return None


__all__ = ["TH2E", "PapouchDevice", "Quido", "create_device"]
