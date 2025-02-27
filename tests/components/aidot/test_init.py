"""Test aidot."""

from unittest.mock import AsyncMock, MagicMock, patch

from aidot.const import CONF_ACCESS_TOKEN, CONF_COUNTRY, CONF_LOGIN_INFO, CONF_REGION
import pytest

from homeassistant.components.aidot.__init__ import (
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.aidot.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import Mock

TEST_DEFAULT = {
    CONF_LOGIN_INFO: {
        CONF_USERNAME: "test",
        CONF_PASSWORD: "password",
        CONF_REGION: "us",
        CONF_COUNTRY: "United States",
        CONF_ACCESS_TOKEN: "token",
    }
}


@pytest.fixture(name="aidot_init", autouse=True)
def aidot_init_fixture():
    """Aidot and entry setup."""
    with (
        patch(
            "homeassistant.components.aidot.coordinator.Discover.fetch_devices_info",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.aidot.__init__.AidotCoordinator.async_config_entry_first_refresh",
            new=AsyncMock(),
        ),
    ):
        yield


async def test_async_setup_entry_calls_async_forward_entry_setups(
    hass: HomeAssistant,
) -> None:
    """Test that async_setup_entry calls async_forward_entry_setups correctly."""

    mock_entry = Mock(spec=ConfigEntry)
    mock_entry.domain = DOMAIN
    mock_entry.data = TEST_DEFAULT
    mock_entry.entry_id = "test"

    mock_data = {}
    hass.data = MagicMock()
    hass.data.setdefault = MagicMock(side_effect=mock_data.setdefault)
    with (
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
    ):
        await async_setup_entry(hass, mock_entry)
        hass.config_entries.async_forward_entry_setups.assert_called_once_with(
            mock_entry, ["light"]
        )


async def test_async_setup_entry_returns_true(hass: HomeAssistant) -> None:
    """Test that async_setup_entry returns True."""
    mock_entry = Mock(spec=ConfigEntry)
    mock_entry.domain = DOMAIN
    mock_entry.data = TEST_DEFAULT
    mock_entry.entry_id = "test"

    mock_data = {}
    hass.data = MagicMock()
    hass.data.setdefault = MagicMock(side_effect=mock_data.setdefault)
    with (
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
    ):
        result = await async_setup_entry(hass, mock_entry)
    assert result is True


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test that async_unload_entry unloads the component correctly."""

    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.domain = DOMAIN
    mock_entry.data = TEST_DEFAULT
    mock_entry.entry_id = "test"

    hass.data = MagicMock()
    with patch.object(
        hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
    ) as mock_unload:
        await async_unload_entry(hass, mock_entry)
        mock_unload.assert_called_once_with(mock_entry, ["light"])


async def test_async_unload_entry_fails(hass: HomeAssistant) -> None:
    """Test that async_unload_entry handles failure correctly."""
    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.domain = DOMAIN
    mock_entry.data = TEST_DEFAULT
    mock_entry.entry_id = "test"

    mock_data = {}
    hass.data = MagicMock()
    hass.data.setdefault = MagicMock(side_effect=mock_data.setdefault)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ) as mock_unload:
        result = await async_unload_entry(hass, mock_entry)
        mock_unload.assert_called_once_with(mock_entry, ["light"])
        assert result is False
        assert hass.data.get(DOMAIN) is not None
