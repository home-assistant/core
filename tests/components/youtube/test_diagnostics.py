"""Tests for the diagnostics data provided by the YouTube integration."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.youtube.const import (
    ATTR_DESCRIPTION,
    ATTR_LATEST_VIDEO,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: ComponentSetup,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot


async def test_diagnostics_does_not_mutate_coordinator_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: ComponentSetup,
) -> None:
    """Test that fetching diagnostics does not mutate the coordinator's data.

    Previously, diagnostics called .pop(ATTR_DESCRIPTION) directly on the
    coordinator's data dict, permanently removing the description from the
    live data after the first diagnostics fetch.
    """
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data

    descriptions_before = {
        channel_id: channel_data[ATTR_LATEST_VIDEO][ATTR_DESCRIPTION]
        for channel_id, channel_data in coordinator.data.items()
        if channel_data.get(ATTR_LATEST_VIDEO) is not None
    }

    assert descriptions_before, (
        "Test setup should include at least one channel with a latest video"
    )

    await get_diagnostics_for_config_entry(hass, hass_client, entry)

    for channel_id, description in descriptions_before.items():
        assert (
            coordinator.data[channel_id][ATTR_LATEST_VIDEO][ATTR_DESCRIPTION]
            == description
        ), (
            f"Coordinator data was mutated for channel {channel_id}: "
            "description was removed by diagnostics fetch"
        )


async def test_diagnostics_description_excluded_from_output(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: ComponentSetup,
) -> None:
    """Test that description is excluded from diagnostics output.

    The description is intentionally redacted from diagnostics output,
    but this must be done without mutating the coordinator's live data.
    """
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    for channel_id, channel_data in result.items():
        latest_video = channel_data.get(ATTR_LATEST_VIDEO)
        if latest_video is not None:
            assert ATTR_DESCRIPTION not in latest_video, (
                f"Description should be redacted from diagnostics output "
                f"for channel {channel_id}"
            )


async def test_diagnostics_no_latest_video(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: ComponentSetup,
) -> None:
    """Test diagnostics when a channel has no latest video.

    Previously, the code called .get(ATTR_LATEST_VIDEO, {}).pop(...) which
    silently operated on a throwaway empty dict when ATTR_LATEST_VIDEO was None.
    This test ensures the None case is handled explicitly and doesn't error.
    """
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data

    channel_id = next(iter(coordinator.data))
    original_data = coordinator.data[channel_id].copy()
    coordinator.data[channel_id] = {**original_data, ATTR_LATEST_VIDEO: None}

    try:
        result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
        assert result[channel_id][ATTR_LATEST_VIDEO] is None
    finally:
        coordinator.data[channel_id] = original_data
