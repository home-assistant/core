"""Tests for the Qube Heat Pump hub."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.qube_heatpump.hub import QubeHub
from homeassistant.core import HomeAssistant


async def test_hub_properties(hass: HomeAssistant) -> None:
    """Test hub properties."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.connect = AsyncMock(return_value=True)

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, "qube1")

        assert hub.host == "1.2.3.4"
        assert hub.unit == 1
        assert hub.label == "qube1"
        assert hub.entry_id == "test_entry_id"
        assert hub.resolved_ip is None
        assert hub.err_connect == 0


async def test_hub_default_label(hass: HomeAssistant) -> None:
    """Test hub with default label."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, None)

        assert hub.label == "qube1"


async def test_hub_connect_success(hass: HomeAssistant) -> None:
    """Test successful connection."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.connect = AsyncMock(return_value=True)

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, "qube1")
        await hub.async_connect()

        client.connect.assert_called_once()
        assert hub.err_connect == 0


async def test_hub_connect_failure_increments_error(hass: HomeAssistant) -> None:
    """Test connection failure increments error counter and backoff."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.connect = AsyncMock(return_value=False)

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, "qube1")
        await hub.async_connect()

        assert hub.err_connect == 1
        assert hub._connect_backoff_s > 0


async def test_hub_connect_backoff_doubles(hass: HomeAssistant) -> None:
    """Test connection backoff doubles on repeated failures."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.connect = AsyncMock(return_value=False)

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, "qube1")

        await hub.async_connect()
        first_backoff = hub._connect_backoff_s

        hub._next_connect_ok_at = 0
        await hub.async_connect()
        second_backoff = hub._connect_backoff_s

        assert second_backoff == first_backoff * 2


async def test_hub_connect_backoff_max(hass: HomeAssistant) -> None:
    """Test connection backoff doesn't exceed max."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.connect = AsyncMock(return_value=False)

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, "qube1")
        hub._connect_backoff_s = 50.0
        hub._next_connect_ok_at = 0

        await hub.async_connect()

        assert hub._connect_backoff_s <= hub._connect_backoff_max_s


async def test_hub_connect_success_resets_backoff(hass: HomeAssistant) -> None:
    """Test successful connection resets backoff."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.connect = AsyncMock(return_value=True)

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, "qube1")
        hub._connect_backoff_s = 30.0
        hub._next_connect_ok_at = 100.0

        await hub.async_connect()

        assert hub._connect_backoff_s == 0.0
        assert hub._next_connect_ok_at == 0.0


async def test_hub_close(hass: HomeAssistant) -> None:
    """Test hub close."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.close = AsyncMock(return_value=None)

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, "qube1")
        await hub.async_close()

        client.close.assert_called_once()


async def test_hub_get_all_data(hass: HomeAssistant) -> None:
    """Test hub get_all_data."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.connect = AsyncMock(return_value=True)
        client.get_all_data = AsyncMock(return_value=MagicMock())

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, "qube1")
        result = await hub.async_get_all_data()

        assert result is not None
        client.connect.assert_called()
        client.get_all_data.assert_called()


async def test_hub_get_all_data_connection_fails(hass: HomeAssistant) -> None:
    """Test hub get_all_data returns None when connection fails."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1
        client.connect = AsyncMock(return_value=False)

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, "qube1")
        result = await hub.async_get_all_data()

        assert result is None


async def test_hub_set_unit_id(hass: HomeAssistant) -> None:
    """Test hub set_unit_id."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, "qube1")
        hub.set_unit_id(5)

        assert client.unit == 5


async def test_hub_resolve_ip(hass: HomeAssistant) -> None:
    """Test hub async_resolve_ip."""
    with patch(
        "homeassistant.components.qube_heatpump.hub.QubeClient", autospec=True
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.host = "1.2.3.4"
        client.port = 502
        client.unit = 1

        hub = QubeHub(hass, "1.2.3.4", 502, "test_entry_id", 1, "qube1")
        await hub.async_resolve_ip()

        # This is a no-op in current implementation, just verify no exception
