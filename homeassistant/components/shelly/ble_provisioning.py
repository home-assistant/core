"""BLE provisioning helpers for Shelly integration."""

from __future__ import annotations

import asyncio
import logging
from typing import cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac

from .const import PROVISIONING_FUTURES

_LOGGER = logging.getLogger(__name__)


@callback
def async_get_provisioning_futures(
    hass: HomeAssistant,
) -> dict[str, asyncio.Future[str]]:
    """Get the provisioning futures registry, creating it if needed.

    This is a helper function for internal use.
    It ensures the registry exists without requiring async_setup to run first.
    """
    return cast(
        dict[str, asyncio.Future[str]], hass.data.setdefault(PROVISIONING_FUTURES, {})
    )


@callback
def async_register_zeroconf_flow(hass: HomeAssistant, mac: str, flow_id: str) -> None:
    """Register a zeroconf flow for a device that was provisioned via BLE.

    Called by zeroconf discovery when it finds a device that may have been
    provisioned via BLE. If BLE provisioning is waiting for this device,
    the Future will be resolved with the flow_id.

    Args:
        hass: Home Assistant instance
        mac: Device MAC address (will be normalized)
        flow_id: Config flow ID to chain to

    """
    registry = async_get_provisioning_futures(hass)
    normalized_mac = format_mac(mac)

    future = registry.get(normalized_mac)
    if not future:
        _LOGGER.debug(
            "No BLE provisioning future found for %s (flow_id %s)",
            normalized_mac,
            flow_id,
        )
        return

    if future.done():
        _LOGGER.debug(
            "Future for %s already done, ignoring flow_id %s",
            normalized_mac,
            flow_id,
        )
        return

    _LOGGER.debug(
        "Resolving BLE provisioning future for %s with flow_id %s",
        normalized_mac,
        flow_id,
    )
    future.set_result(flow_id)
