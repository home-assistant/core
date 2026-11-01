"""Tests for the TOLO Sauna buttons."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "button.tolo_sauna_next_color"


@pytest.fixture(autouse=True)
def button_platform_only() -> Generator[None]:
    """Only set up the button platform."""
    with patch("homeassistant.components.tolo.PLATFORMS", [Platform.BUTTON]):
        yield


async def test_button_unavailable_on_failed_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the button becomes unavailable when an update fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    mock_tolo_client.get_status.side_effect = TimeoutError
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_tolo_client.get_status.side_effect = None
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN
