"""Test clock synchronization alongside measurement polling."""

from unittest.mock import MagicMock, call

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("elapsed", "expected_epochs"),
    [
        pytest.param(15, [1767225600], id="fifteen-second-poll"),
        pytest.param(59.999, [1767225600], id="before-deadline"),
        pytest.param(60, [1767225600, 1767225660], id="at-deadline"),
        pytest.param(65, [1767225600, 1767225665], id="after-deadline"),
    ],
)
async def test_clock_sync_throttle(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    elapsed: float,
    expected_epochs: list[int],
) -> None:
    """Send integer UTC time at setup and at most once per 60 seconds."""
    freezer.move_to("2026-01-01T00:00:00.500000+00:00")
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.command.assert_awaited_once_with(
        "time", epoch=1767225600, uncertainty_ms=1000
    )

    freezer.tick(elapsed)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_client.refresh.await_count == 2
    assert mock_client.command.await_args_list == [
        call("time", epoch=epoch, uncertainty_ms=1000) for epoch in expected_epochs
    ]
    await hass.config_entries.async_unload(config_entry.entry_id)
