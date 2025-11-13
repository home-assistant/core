"""BLE provisioning helpers for Shelly integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.util.hass_dict import HassKey

_LOGGER = logging.getLogger(__name__)


@dataclass
class ProvisioningState:
    """State for tracking zeroconf discovery during BLE provisioning."""

    event: asyncio.Event = field(default_factory=asyncio.Event)
    host: str | None = None
    port: int | None = None


PROVISIONING_FUTURES: HassKey[dict[str, ProvisioningState]] = HassKey(
    "shelly_provisioning_futures"
)


@callback
def async_get_provisioning_registry(
    hass: HomeAssistant,
) -> dict[str, ProvisioningState]:
    """Get the provisioning registry, creating it if needed.

    This is a helper function for internal use.
    It ensures the registry exists without requiring async_setup to run first.
    """
    return hass.data.setdefault(PROVISIONING_FUTURES, {})


@callback
def async_register_zeroconf_discovery(
    hass: HomeAssistant, mac: str, host: str, port: int
) -> None:
    """Register a zeroconf discovery for a device that was provisioned via BLE.

    Called by zeroconf discovery when it finds a device that may have been
    provisioned via BLE. If BLE provisioning is waiting for this device,
    the host and port will be stored (replacing any previous values).

    Multiple zeroconf discoveries can happen (Shelly service, HTTP service, etc.)
    and the last one wins.

    Args:
        hass: Home Assistant instance
        mac: Device MAC address (will be normalized)
        host: Device IP address/hostname from zeroconf
        port: Device port from zeroconf

    """
    registry = async_get_provisioning_registry(hass)
    normalized_mac = format_mac(mac)

    state = registry.get(normalized_mac)
    if not state:
        _LOGGER.debug(
            "No BLE provisioning state found for %s (host %s, port %s)",
            normalized_mac,
            host,
            port,
        )
        return

    _LOGGER.debug(
        "Registering zeroconf discovery for %s at %s:%s (replacing previous)",
        normalized_mac,
        host,
        port,
    )

    # Store host and port (replacing any previous values) and signal the event
    state.host = host
    state.port = port
    state.event.set()
