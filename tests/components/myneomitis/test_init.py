"""Tests for the MyNeomitis integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.myneomitis import (
    MyNeomitisRuntimeData,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


class DummyEntry:
    """Dummy class to simulate a ConfigEntry."""

    def __init__(self, entry_id: str, data: dict) -> None:
        """Initialize the DummyEntry."""
        self.entry_id = entry_id
        self.data = data
        self.unique_id = entry_id
        self.runtime_data = None
        self._on_unload_callbacks: list = []

    def async_on_unload(self, callback) -> None:
        """Register a callback to be called when the entry is unloaded."""
        self._on_unload_callbacks.append(callback)


async def test_minimal_setup(hass: HomeAssistant) -> None:
    """Test the minimal setup of the MyNeomitis integration."""

    entry = ConfigEntry(
        version=1,
        minor_version=1,
        entry_id="test-entry",
        domain="myneomitis",
        title="MyNeomitis",
        data={"email": "test@example.com", "password": "testpass"},
        options={},
        source="user",
        unique_id="test-unique-id",
        disabled_by=None,
        pref_disable_new_entities=False,
        pref_disable_polling=False,
        discovery_keys=[],
        subentries_data={},
    )
    await hass.config_entries.async_add(entry)

    with (
        patch("pyaxencoapi.PyAxencoAPI") as mock_api_class,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=None),
        ),
    ):
        mock_api = mock_api_class.return_value
        mock_api.login = AsyncMock()
        mock_api.connect_websocket = AsyncMock()
        mock_api.get_devices = AsyncMock(return_value=[])
        mock_api.disconnect_websocket = AsyncMock()

        result = await async_setup_entry(hass, entry)

    assert result is True


async def test_setup_entry_raises_on_login_fail(hass: HomeAssistant) -> None:
    """Test that async_setup_entry raises ConfigEntryNotReady if login fails."""
    entry = DummyEntry("test-entry", {"email": "a@b.c", "password": "pw"})

    with patch("pyaxencoapi.PyAxencoAPI") as api_cls:
        api = api_cls.return_value
        api.login = AsyncMock(side_effect=TimeoutError("fail-login"))

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


async def test_unload_entry_success(hass: HomeAssistant) -> None:
    """Test that async_unload_entry unloads and disconnects cleanly."""
    entry = DummyEntry("test-entry", {"email": "u@v.w", "password": "pw"})

    api = AsyncMock()
    entry.runtime_data = MyNeomitisRuntimeData(api=api, devices=[])

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    result = await async_unload_entry(hass, entry)

    assert result is True
    api.disconnect_websocket.assert_awaited_once()


async def test_unload_entry_failure(hass: HomeAssistant) -> None:
    """Test that async_unload_entry returns False if unload fails."""
    entry = DummyEntry("test-entry", {"email": "u@v.w", "password": "pw"})
    api = AsyncMock()
    entry.runtime_data = MyNeomitisRuntimeData(api=api, devices=[])

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    result = await async_unload_entry(hass, entry)

    assert result is False
    api.disconnect_websocket.assert_not_awaited()


async def test_setup_entry_success_populates_data_and_forwards(
    hass: HomeAssistant,
) -> None:
    """Test happy path async_setup_entry."""
    entry = DummyEntry("e1", {"email": "u@d.e", "password": "pw"})

    with (
        patch("pyaxencoapi.PyAxencoAPI") as api_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=None),
        ) as forward,
    ):
        api = api_cls.return_value
        api.login = AsyncMock()
        api.connect_websocket = AsyncMock()
        api.get_devices = AsyncMock(return_value=[{"id": 1}, {"id": 2}])
        api.disconnect_websocket = AsyncMock()

        result = await async_setup_entry(hass, entry)

        assert result is True
        assert entry.runtime_data is not None
        assert isinstance(entry.runtime_data, MyNeomitisRuntimeData)
        assert entry.runtime_data.devices == [{"id": 1}, {"id": 2}]
        forward.assert_awaited_once()


@pytest.mark.parametrize("fail_method", ["login", "connect_websocket", "get_devices"])
async def test_setup_entry_failure_raises_on_any_api_error(
    hass: HomeAssistant, fail_method: str
) -> None:
    """If any API method fails, ConfigEntryNotReady is raised."""
    entry = DummyEntry("e2", {"email": "a@b.c", "password": "pw"})
    with patch("pyaxencoapi.PyAxencoAPI") as api_cls:
        api = api_cls.return_value

        api.login = AsyncMock()
        api.connect_websocket = AsyncMock()
        api.get_devices = AsyncMock()
        api.disconnect_websocket = AsyncMock()

        setattr(api, fail_method, AsyncMock(side_effect=ConnectionError("boom")))

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


async def test_unload_entry_logs_on_disconnect_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """When disconnecting the websocket fails, an error is logged."""
    entry = DummyEntry("e3", {"email": "x@y.z", "password": "pw"})

    api = AsyncMock()
    api.disconnect_websocket = AsyncMock(side_effect=TimeoutError("to"))
    entry.runtime_data = MyNeomitisRuntimeData(api=api, devices=[])
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    caplog.set_level("ERROR")
    result = await async_unload_entry(hass, entry)

    assert result is True
    assert "Error while disconnecting WebSocket" in caplog.text


async def test_homeassistant_stop_disconnects_websocket(hass: HomeAssistant) -> None:
    """Test that WebSocket is disconnected on Home Assistant stop event."""

    entry = DummyEntry("e4", {"email": "u@d.e", "password": "pw"})

    with (
        patch("pyaxencoapi.PyAxencoAPI") as api_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=None),
        ),
    ):
        api = api_cls.return_value
        api.login = AsyncMock()
        api.connect_websocket = AsyncMock()
        api.get_devices = AsyncMock(return_value=[])
        api.disconnect_websocket = AsyncMock()

        await async_setup_entry(hass, entry)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

        api.disconnect_websocket.assert_awaited_once()


async def test_homeassistant_stop_logs_on_disconnect_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that WebSocket disconnect errors are logged on HA stop."""

    entry = DummyEntry("e5", {"email": "u@d.e", "password": "pw"})

    with (
        patch("pyaxencoapi.PyAxencoAPI") as api_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=None),
        ),
    ):
        api = api_cls.return_value
        api.login = AsyncMock()
        api.connect_websocket = AsyncMock()
        api.get_devices = AsyncMock(return_value=[])
        api.disconnect_websocket = AsyncMock(
            side_effect=TimeoutError("disconnect failed")
        )

        await async_setup_entry(hass, entry)

        caplog.set_level("ERROR")

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

        assert "Error while disconnecting WebSocket" in caplog.text
