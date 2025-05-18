"""Tests for the Sonos statistics."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_statistics_duplicate(
    hass: HomeAssistant,
    async_autosetup_sonos,
    soco,
    device_properties_event,
    config_entry: MockConfigEntry,
) -> None:
    """Test Sonos statistics."""
    speaker = list(config_entry.runtime_data.sonos_data.discovered.values())[0]

    subscription = soco.deviceProperties.subscribe.return_value
    sub_callback = subscription.callback

    # Update the speaker with a callback event
    sub_callback(device_properties_event)
    await hass.async_block_till_done()

    report = speaker.event_stats.report()
    assert report["DeviceProperties"]["received"] == 1
    assert report["DeviceProperties"]["duplicates"] == 0
    assert report["DeviceProperties"]["processed"] == 1

    # Ensure a duplicate is registered in the statistics
    sub_callback(device_properties_event)
    await hass.async_block_till_done()

    report = speaker.event_stats.report()
    assert report["DeviceProperties"]["received"] == 2
    assert report["DeviceProperties"]["duplicates"] == 1
    assert report["DeviceProperties"]["processed"] == 1
