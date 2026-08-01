"""Tests for Clicky init."""

from __future__ import annotations

from unittest.mock import ANY, AsyncMock, Mock, patch

from homeassistant.components.clicky.const import CONF_SITE_ID, CONF_SITEKEY, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: "12345",
            CONF_SITEKEY: "abcdef",
        },
    )

    entry.add_to_hass(hass)

    mock_client = Mock()
    mock_client.query = AsyncMock()

    mock_coordinator = Mock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.async_add_listener.return_value = Mock()

    with (
        patch(
            "homeassistant.components.clicky.ClickyClient",
            return_value=mock_client,
        ) as client_cls,
        patch(
            "homeassistant.components.clicky.ClickyCoordinator",
            return_value=mock_coordinator,
        ) as coordinator_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ) as forward,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    client_cls.assert_called_once_with(site_id="12345", sitekey="abcdef", session=ANY)

    coordinator_cls.assert_called_once_with(
        hass,
        entry,
        mock_client,
    )

    mock_coordinator.async_config_entry_first_refresh.assert_awaited_once()

    forward.assert_awaited_once()

    assert entry.runtime_data is mock_coordinator
