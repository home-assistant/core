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

    # settings are being fetched now, because ctor isn't async
    if "Quido" in device:
        settings = await api_client.fetch_settings()
        return Quido(api_client, settings, info)
    if "TH2E" in device:
        settings = await api_client.fetch_settings()
        return TH2E(api_client, settings, info)
    if "TME" in device:
        fresh = await api_client.fetch_data()
        return TME(api_client, info, fresh)

    return None


__all__ = ["TH2E", "TME", "PapouchDevice", "Quido", "create_device"]
