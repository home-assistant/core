"""This file is used as a hub for imports."""

import logging

from ..client import PapouchTransport
from .base import PapouchDevice
from .quido import async_setup_quido
from .th2e import async_setup_th2e
from .tme import async_setup_tme

_LOGGER = logging.getLogger(__name__)


async def create_device(api_client: PapouchTransport) -> PapouchDevice | None:
    """Function that creates proper device instance.

    Returns "None" if the device is not supported.
    """

    device_name = await api_client.get_device_name()

    if device_name is None:
        return None

    if "Quido" in device_name:
        return await async_setup_quido(api_client)
    if "TH2E" in device_name:
        return await async_setup_th2e(api_client)
    if "TME" in device_name:
        return await async_setup_tme(api_client)
    # if "Papago" in device:
    #     return None

    return None


__all__ = ["PapouchDevice", "create_device"]
