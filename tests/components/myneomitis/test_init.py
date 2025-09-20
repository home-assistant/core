"""Tests for the MyNeomitis integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.myneomitis import (
    async_reload_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.myneomitis.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import pyaxencoapi


class DummyEntry:
    """Dummy class to simulate a ConfigEntry."""

    def __init__(self, entry_id: str, data: dict) -> None:
        """Initialize the DummyEntry."""
        self.entry_id = entry_id
        self.data = data
        self.unique_id = entry_id


@pytest.mark.asyncio
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
        patch(pyaxencoapi.PyAxencoAPI) as mock_api_class,
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

        result = await async_setup_entry(hass, entry)

    assert result is True


@pytest.mark.asyncio
async def test_setup_entry_raises_on_login_fail(hass: HomeAssistant) -> None:
    """Test that async_setup_entry raises ConfigEntryNotReady if login fails."""
    entry = DummyEntry("test-entry", {"email": "a@b.c", "password": "pw"})

    with patch(pyaxencoapi.PyAxencoAPI) as api_cls:
        api = api_cls.return_value
        api.login = AsyncMock(side_effect=Exception("fail-login"))

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_unload_entry_success(hass: HomeAssistant) -> None:
    """Test that async_unload_entry unloads and disconnects cleanly."""
    entry = DummyEntry("test-entry", {"email": "u@v.w", "password": "pw"})

    api = AsyncMock()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"api": api, "devices": []}

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    result = await async_unload_entry(hass, entry)

    assert result is True
    api.disconnect_websocket.assert_awaited_once()
    assert entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_unload_entry_failure(hass: HomeAssistant) -> None:
    """Test that async_unload_entry returns False if unload fails."""
    entry = DummyEntry("test-entry", {"email": "u@v.w", "password": "pw"})
    api = AsyncMock()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"api": api, "devices": []}

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    result = await async_unload_entry(hass, entry)

    assert result is False
    api.disconnect_websocket.assert_not_awaited()


@pytest.mark.asyncio
async def test_reload_entry_calls_unload_and_setup(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that async_reload_entry calls unload then setup."""
    entry = DummyEntry("test-entry", {"email": "x@y.z", "password": "pw"})

    mock_unload = AsyncMock()
    mock_setup = AsyncMock()

    monkeypatch.setattr(
        "homeassistant.components.myneomitis.async_unload_entry", mock_unload
    )
    monkeypatch.setattr(
        "homeassistant.components.myneomitis.async_setup_entry", mock_setup
    )

    await async_reload_entry(hass, entry)

    assert mock_unload.await_count == 1
    assert mock_setup.await_count == 1


@pytest.mark.asyncio
async def test_async_setup_returns_true(hass: HomeAssistant) -> None:
    """Simple test to check if async_setup returns True."""
    assert await async_setup(hass, {}) is True


@pytest.mark.asyncio
async def test_setup_entry_success_populates_data_and_forwards(
    hass: HomeAssistant,
) -> None:
    """Test happy path async_setup_entry."""
    entry = DummyEntry("e1", {"email": "u@d.e", "password": "pw"})

    with (
        patch(pyaxencoapi.PyAxencoAPI) as api_cls,
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

        result = await async_setup_entry(hass, entry)

        assert result is True
        assert entry.entry_id in hass.data[DOMAIN]
        assert hass.data[DOMAIN][entry.entry_id]["devices"] == [{"id": 1}, {"id": 2}]
        forward.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fail_method", [("login",), ("connect_websocket",), ("get_devices",)]
)
async def test_setup_entry_failure_raises_on_any_api_error(
    hass: HomeAssistant, fail_method: str
) -> None:
    """If any API method fails, ConfigEntryNotReady is raised."""
    entry = DummyEntry("e2", {"email": "a@b.c", "password": "pw"})
    with patch(pyaxencoapi.PyAxencoAPI) as api_cls:
        api = api_cls.return_value
        setattr(api, fail_method, AsyncMock(side_effect=Exception("boom")))

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_unload_entry_logs_on_disconnect_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """When disconnecting the websocket fails, an error is logged."""
    entry = DummyEntry("e3", {"email": "x@y.z", "password": "pw"})

    api = AsyncMock()
    api.disconnect_websocket = AsyncMock(side_effect=TimeoutError("to"))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"api": api, "devices": []}
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    caplog.set_level("ERROR")
    result = await async_unload_entry(hass, entry)

    assert result is True
    assert "Error while disconnecting WebSocket" in caplog.text
    assert entry.entry_id not in hass.data[DOMAIN]
