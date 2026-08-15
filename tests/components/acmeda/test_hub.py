"""Tests for the Acmeda hub module."""

from unittest.mock import MagicMock, patch

import aiopulse
import pytest

from homeassistant.components.acmeda.helpers import async_add_acmeda_entities
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_hub_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
) -> None:
    """Test hub is set up correctly with properties and start."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hub = mock_config_entry.runtime_data
    assert hub.title == "hub-id (127.0.0.1)"
    assert hub.host == "127.0.0.1"
    mock_hub.run.assert_called_once()


async def test_hub_reset(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
) -> None:
    """Test hub reset cleans up correctly."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_hub.callback_unsubscribe.assert_called()
    mock_hub.stop.assert_called_once()


@pytest.mark.parametrize(
    ("update_type", "should_update"),
    [
        (aiopulse.UpdateType.rollers, True),
        (aiopulse.UpdateType.info, False),
    ],
)
async def test_async_notify_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
    mock_roller: MagicMock,
    update_type: aiopulse.UpdateType,
    should_update: bool,
) -> None:
    """Test async_notify_update behavior for different update types."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    notify_update = mock_hub.callback_subscribe.call_args[0][0]

    with patch("homeassistant.components.acmeda.hub.update_devices") as mock_update:
        notify_update(update_type)
        await hass.async_block_till_done()
        if should_update:
            mock_update.assert_called_once_with(
                hass, mock_config_entry, mock_hub.rollers
            )
        else:
            mock_update.assert_not_called()


async def test_hub_api_none_paths(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub: MagicMock,
) -> None:
    """Test hub behavior when api is None after unload."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hub = mock_config_entry.runtime_data

    # Unload sets api to None
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # title returns host when api is None
    assert hub.title == "127.0.0.1"

    # async_start returns early when api is None (no api.run() called)
    mock_hub.run.reset_mock()
    await hub.async_start()
    mock_hub.run.assert_not_called()

    # async_reset returns False when api is None
    assert await hub.async_reset() is False

    # async_notify_update returns early when api is None (no update_devices called)
    with patch("homeassistant.components.acmeda.hub.update_devices") as mock_update:
        await hub.async_notify_update(aiopulse.UpdateType.rollers)
        mock_update.assert_not_called()

    # async_add_acmeda_entities returns early when api is None
    mock_add_entities = MagicMock()
    async_add_acmeda_entities(
        hass, MagicMock(), mock_config_entry, set(), mock_add_entities
    )
    mock_add_entities.assert_not_called()
