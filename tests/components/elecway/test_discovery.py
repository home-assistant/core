"""Test discovery filtering and resource cleanup."""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zeroconf import ServiceStateChange, Zeroconf

from homeassistant.components.elecway.discovery import (
    async_discover,
    storage_serial_number,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import SERIAL


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param(
            f"EwayEnergyStorage-{SERIAL}._http._tcp.local.", SERIAL, id="storage"
        ),
        pytest.param("EwayCS-TFT-id_sn._http._tcp.local.", None, id="charger"),
        pytest.param(
            "EwayEnergyStorage-SN._other._tcp.local.", None, id="wrong-service"
        ),
        pytest.param("EwayEnergyStorage-._http._tcp.local.", None, id="empty-serial"),
    ],
)
def test_storage_identity(name: str, expected: str | None) -> None:
    """Only the storage service convention supplies a serial number."""
    assert storage_serial_number(name) == expected


@pytest.mark.parametrize(
    ("resolved", "serials"),
    [
        pytest.param(True, [SERIAL], id="resolved"),
        pytest.param(False, [], id="resolution-timeout"),
    ],
)
async def test_discover(
    hass: HomeAssistant,
    discovery: ZeroconfServiceInfo,
    resolved: bool,
    serials: list[str],
) -> None:
    """Filter unrelated and removed services, then resolve the remaining device."""

    def browser_created(
        zeroconf: Zeroconf,
        service_type: str,
        handlers: list[Callable[[Zeroconf, str, str, ServiceStateChange], None]],
    ) -> MagicMock:
        handler = handlers[0]
        handler(zeroconf, service_type, discovery.name, ServiceStateChange.Added)
        handler(
            zeroconf,
            service_type,
            "Printer._http._tcp.local.",
            ServiceStateChange.Added,
        )
        handler(
            zeroconf,
            service_type,
            "EwayEnergyStorage-removed._http._tcp.local.",
            ServiceStateChange.Added,
        )
        handler(
            zeroconf,
            service_type,
            "EwayEnergyStorage-removed._http._tcp.local.",
            ServiceStateChange.Removed,
        )
        return browser

    browser = MagicMock()
    browser.async_cancel = AsyncMock()
    with (
        patch("homeassistant.components.elecway.discovery.async_get_async_instance"),
        patch(
            "homeassistant.components.elecway.discovery.AsyncServiceBrowser",
            side_effect=browser_created,
        ),
        patch("homeassistant.components.elecway.discovery.asyncio.sleep"),
        patch("homeassistant.components.elecway.discovery.AsyncServiceInfo") as info,
        patch(
            "homeassistant.components.elecway.discovery.info_from_service",
            return_value=discovery,
        ),
    ):
        info.return_value.async_request = AsyncMock(return_value=resolved)
        assert list(await async_discover(hass)) == serials
        info.assert_called_once_with("_http._tcp.local.", discovery.name)
        browser.async_cancel.assert_awaited_once()


async def test_cancel_discovery(hass: HomeAssistant) -> None:
    """Cancelling a scan stops the browser without closing HA's shared instance."""
    with (
        patch(
            "homeassistant.components.elecway.discovery.async_get_async_instance"
        ) as instance,
        patch(
            "homeassistant.components.elecway.discovery.AsyncServiceBrowser"
        ) as browser,
        patch(
            "homeassistant.components.elecway.discovery.asyncio.sleep",
            side_effect=asyncio.CancelledError,
        ),
    ):
        browser.return_value.async_cancel = AsyncMock()
        with pytest.raises(asyncio.CancelledError):
            await async_discover(hass)
        browser.return_value.async_cancel.assert_awaited_once()
        instance.return_value.async_close.assert_not_called()
