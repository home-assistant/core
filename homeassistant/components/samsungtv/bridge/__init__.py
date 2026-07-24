"""samsungctl and samsungtvws bridge classes."""

from typing import Any

from homeassistant.core import HomeAssistant

from ..const import (
    ENCRYPTED_WEBSOCKET_PORT,
    LEGACY_PORT,
    LOGGER,
    METHOD_ENCRYPTED_WEBSOCKET,
    METHOD_LEGACY,
    METHOD_WEBSOCKET,
    RESULT_CANNOT_CONNECT,
    RESULT_SUCCESS,
    SUCCESSFUL_RESULTS,
    WEBSOCKET_PORTS,
)
from .base import SamsungTVBridge, mac_from_device_info, model_requires_encryption
from .encrypted import SamsungTVEncryptedBridge
from .legacy import SamsungTVLegacyBridge
from .websocket import SamsungTVWSBaseBridge, SamsungTVWSBridge

__all__ = [
    "SamsungTVBridge",
    "SamsungTVEncryptedBridge",
    "SamsungTVLegacyBridge",
    "SamsungTVWSBaseBridge",
    "SamsungTVWSBridge",
    "async_get_device_info",
    "mac_from_device_info",
    "model_requires_encryption",
]


async def async_get_device_info(
    hass: HomeAssistant,
    host: str,
) -> tuple[str, int | None, str | None, dict[str, Any] | None]:
    """Fetch the port, method, and device info."""
    for port in WEBSOCKET_PORTS:
        bridge = SamsungTVBridge.get_bridge(hass, METHOD_WEBSOCKET, host, port)
        if info := await bridge.async_device_info():
            LOGGER.debug(
                "Fetching rest info via %s was successful: %s, checking for encrypted",
                port,
                info,
            )
            if model_requires_encryption(info.get("device", {}).get("modelName")):
                encrypted_bridge = SamsungTVEncryptedBridge(
                    hass, METHOD_ENCRYPTED_WEBSOCKET, host, ENCRYPTED_WEBSOCKET_PORT
                )
                result = await encrypted_bridge.async_try_connect()
                if result != RESULT_CANNOT_CONNECT:
                    return (
                        result,
                        ENCRYPTED_WEBSOCKET_PORT,
                        METHOD_ENCRYPTED_WEBSOCKET,
                        info,
                    )
            return RESULT_SUCCESS, port, METHOD_WEBSOCKET, info

    bridge = SamsungTVBridge.get_bridge(hass, METHOD_LEGACY, host, LEGACY_PORT)
    result = await bridge.async_try_connect()
    if result in SUCCESSFUL_RESULTS:
        return result, LEGACY_PORT, METHOD_LEGACY, await bridge.async_device_info()

    return result, None, None, None
