"""Tests for the Sonos statistics."""

from homeassistant.components.sonos.const import DATA_SONOS
from homeassistant.core import HomeAssistant


async def test_statistics_duplicate(
    hass: HomeAssistant, async_autosetup_sonos, soco, device_properties_event
) -> None:
    """Test Sonos statistics."""
    speaker = list(hass.data[DATA_SONOS].discovered.values())[0]

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
