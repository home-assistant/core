"""This file is used as a hub for imports."""

import logging

import defusedxml.ElementTree as defused_ET

from ..client import PapouchApiClient
from .base import PapouchDevice
from .quido import Quido
from .th2e import TH2E
from .tme import TME

_LOGGER = logging.getLogger(__name__)


async def create_device(api_client: PapouchApiClient) -> PapouchDevice | None:
    """Function that creates proper device instance.

    Returns "None" if the device is not supported
    or when the device doesn't have proper identification tag.
    """

    info = await api_client.fetch_info()

    try:
        root = defused_ET.fromstring(info)

        heartbeat = None
        for element in root.iter():
            if element.tag.endswith("heartbeat"):
                heartbeat = element
                break

        if heartbeat is None:
            return None

        device = heartbeat.attrib.get("device")
        if not device:
            return None

    except defused_ET.ParseError, AttributeError:
        return None

    _LOGGER.info("Creation of the device: %s", device)

    if "Quido" in device:
        # settings are being fetched now, because ctor isn't async
        settings = await api_client.fetch_settings()
        return Quido(api_client, settings, info)
    if "TH2E" in device:
        return TH2E(api_client, info)
    if "TME" in device:
        return TME(api_client, info)

    return None


__all__ = ["TH2E", "TME", "PapouchDevice", "Quido", "create_device"]
