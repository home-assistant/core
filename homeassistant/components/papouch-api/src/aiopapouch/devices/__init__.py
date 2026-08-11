"""This file is used as a hub for imports."""

from ..client import PapouchTransport
from .base import PapouchDevice
from .papago import async_setup_papago
from .quido import async_setup_quido
from .th2e import async_setup_th2e
from .tme import async_setup_tme

DEVICE_SETUP_HANDLERS = {
    "Quido": async_setup_quido,
    "TH2E": async_setup_th2e,
    "TME": async_setup_tme,
    "Papago": async_setup_papago,
}


def is_device_supported(device_name: str | None) -> bool:
    """Check if the extracted device name matches any supported prefix."""
    if not device_name:
        return False

    return any(prefix in device_name for prefix in DEVICE_SETUP_HANDLERS)


async def create_device(api_client: PapouchTransport) -> PapouchDevice | None:
    """Create a proper device instance dynamically based on the fetched info.

    Returns None if the device is not supported.
    """

    device_name, _ = await api_client.get_device_info()

    if not is_device_supported(device_name):
        return None

    assert device_name is not None

    for prefix, setup_func in DEVICE_SETUP_HANDLERS.items():
        if prefix in device_name:
            return await setup_func(api_client)

    return None


__all__ = ["PapouchDevice", "create_device", "is_device_supported"]
