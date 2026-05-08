"""Tests for iZone discovery service."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.izone.const import STATIC_RECONNECT_INTERVAL
from homeassistant.components.izone.discovery import (
    DiscoveryService,
    async_add_controller_by_ip,
    async_get_device_uid,
    async_start_discovery_service,
)
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


def _make_aiohttp_context(
    json_data: dict | None = None,
    side_effect: Exception | None = None,
) -> MagicMock:
    """Return a mock async context manager for aiohttp session.get()."""
    if side_effect is not None:
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(side_effect=side_effect)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    mock_response = AsyncMock()
    mock_response.raise_for_status = Mock()
    mock_response.json = AsyncMock(return_value=json_data or {})

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


async def test_async_get_device_uid_success(hass: HomeAssistant) -> None:
    """Test successful UID retrieval from an iZone device."""
    mock_session = Mock()
    mock_session.get = Mock(
        return_value=_make_aiohttp_context({"AirStreamDeviceUId": "000013170"})
    )

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await async_get_device_uid(hass, "192.168.2.100")

    assert result == "000013170"


async def test_async_get_device_uid_missing_field(hass: HomeAssistant) -> None:
    """Test ConnectionError when the response lacks AirStreamDeviceUId."""
    mock_session = Mock()
    mock_session.get = Mock(return_value=_make_aiohttp_context({"OtherField": "value"}))

    with (
        patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(ConnectionError),
    ):
        await async_get_device_uid(hass, "192.168.2.100")


async def test_async_get_device_uid_network_error(hass: HomeAssistant) -> None:
    """Test ConnectionError when the device cannot be reached."""
    mock_session = Mock()
    mock_session.get = Mock(
        return_value=_make_aiohttp_context(
            side_effect=aiohttp.ClientError("network error")
        )
    )

    with (
        patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(ConnectionError),
    ):
        await async_get_device_uid(hass, "192.168.2.100")


async def test_async_add_controller_by_ip_fetches_uid_when_none(
    hass: HomeAssistant,
) -> None:
    """Test that async_add_controller_by_ip fetches the UID when not provided."""
    mock_ctrl = Mock()
    mock_ctrl._refresh_address = Mock()

    with patch(
        "homeassistant.components.izone.discovery.pizone.discovery", autospec=True
    ) as mock_pizone_disco:
        mock_pizone_disco.return_value.start_discovery = AsyncMock()
        mock_pizone_disco.return_value.close = AsyncMock()
        mock_pizone_disco.return_value.controllers = {}

        disco = await async_start_discovery_service(hass)

        with (
            patch(
                "homeassistant.components.izone.discovery.async_get_device_uid",
                return_value="000013170",
            ) as mock_get_uid,
            patch.object(
                disco, "async_register_controller", return_value=mock_ctrl
            ) as mock_register,
        ):
            result = await async_add_controller_by_ip(hass, "192.168.2.100")

    mock_get_uid.assert_called_once_with(hass, "192.168.2.100")
    mock_register.assert_called_once_with("192.168.2.100", "000013170")
    assert result is mock_ctrl


async def test_discovery_service_register_existing_controller(
    hass: HomeAssistant,
) -> None:
    """Test registering a controller that is already in the discovery service."""
    disco = DiscoveryService(hass)
    mock_ctrl = Mock()
    mock_ctrl._refresh_address = Mock()

    mock_pi_disco = Mock()
    mock_pi_disco.controllers = {"uid123": mock_ctrl}
    disco.pi_disco = mock_pi_disco

    result = await disco.async_register_controller("192.168.1.100", "uid123")

    assert result is mock_ctrl
    mock_ctrl._refresh_address.assert_called_with("192.168.1.100")
    assert disco._static_hosts["uid123"] == "192.168.1.100"


async def test_discovery_service_register_new_controller(
    hass: HomeAssistant,
) -> None:
    """Test registering a brand-new controller by IP address."""
    disco = DiscoveryService(hass)

    mock_pi_disco = Mock()
    mock_pi_disco.controllers = {}
    mock_pi_disco.controller_discovered = Mock()
    disco.pi_disco = mock_pi_disco

    mock_ctrl = Mock()
    mock_ctrl._refresh_address = Mock()
    mock_ctrl._initialize = AsyncMock()

    with patch(
        "homeassistant.components.izone.discovery.pizone.Controller",
        return_value=mock_ctrl,
    ):
        result = await disco.async_register_controller("192.168.1.100", "uid456")

    assert result is mock_ctrl
    mock_ctrl._initialize.assert_called_once()
    assert mock_pi_disco.controllers["uid456"] is mock_ctrl
    mock_pi_disco.controller_discovered.assert_called_once_with(mock_ctrl)
    assert disco._static_hosts["uid456"] == "192.168.1.100"


async def test_start_keepalive_runs_only_once(hass: HomeAssistant) -> None:
    """Test that _start_keepalive is idempotent — a second call is a no-op."""
    disco = DiscoveryService(hass)
    mock_ctrl = Mock()
    mock_ctrl._refresh_address = Mock()

    mock_pi_disco = Mock()
    mock_pi_disco.controllers = {"uid123": mock_ctrl}
    disco.pi_disco = mock_pi_disco
    disco._static_hosts["uid123"] = "192.168.1.100"

    disco._start_keepalive()
    first_unsub = disco._keepalive_unsub
    assert first_unsub is not None

    disco._start_keepalive()
    assert disco._keepalive_unsub is first_unsub


async def test_keepalive_tick_triggers_reconnect(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the keepalive tick calls _refresh_address when a failure is pending."""
    disco = DiscoveryService(hass)
    mock_ctrl = Mock()
    mock_ctrl._refresh_address = Mock()
    mock_ctrl._fail_exception = Exception("timed out")

    mock_pi_disco = Mock()
    mock_pi_disco.controllers = {"uid123": mock_ctrl}
    disco.pi_disco = mock_pi_disco
    disco._static_hosts["uid123"] = "192.168.1.100"
    disco._start_keepalive()

    freezer.tick(timedelta(seconds=STATIC_RECONNECT_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_ctrl._refresh_address.assert_called_with("192.168.1.100")


async def test_keepalive_tick_skips_healthy_controller(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test keepalive tick does not refresh a controller with no pending failure."""
    disco = DiscoveryService(hass)
    mock_ctrl = Mock()
    mock_ctrl._refresh_address = Mock()
    mock_ctrl._fail_exception = None

    mock_pi_disco = Mock()
    mock_pi_disco.controllers = {"uid123": mock_ctrl}
    disco.pi_disco = mock_pi_disco
    disco._static_hosts["uid123"] = "192.168.1.100"
    disco._start_keepalive()

    freezer.tick(timedelta(seconds=STATIC_RECONNECT_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_ctrl._refresh_address.assert_not_called()


async def test_keepalive_tick_with_pi_disco_none(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test keepalive tick exits early when pi_disco is None."""
    disco = DiscoveryService(hass)
    disco._static_hosts["uid123"] = "192.168.1.100"
    disco._start_keepalive()
    disco.pi_disco = None  # Simulate service torn down

    freezer.tick(timedelta(seconds=STATIC_RECONNECT_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()  # Should not raise


async def test_remove_static_host_stops_keepalive(hass: HomeAssistant) -> None:
    """Test removing the last static host stops the keepalive timer."""
    disco = DiscoveryService(hass)
    disco._static_hosts["uid123"] = "192.168.1.100"
    mock_unsub = Mock()
    disco._keepalive_unsub = mock_unsub

    disco.remove_static_host("uid123")

    assert "uid123" not in disco._static_hosts
    mock_unsub.assert_called_once()
    assert disco._keepalive_unsub is None


async def test_remove_static_host_keeps_keepalive_when_others_remain(
    hass: HomeAssistant,
) -> None:
    """Test keepalive continues when other static hosts remain after removal."""
    disco = DiscoveryService(hass)
    disco._static_hosts["uid1"] = "192.168.1.100"
    disco._static_hosts["uid2"] = "192.168.1.101"
    mock_unsub = Mock()
    disco._keepalive_unsub = mock_unsub

    disco.remove_static_host("uid1")

    assert "uid1" not in disco._static_hosts
    assert "uid2" in disco._static_hosts
    mock_unsub.assert_not_called()
    assert disco._keepalive_unsub is mock_unsub
