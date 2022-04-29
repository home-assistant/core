"""Test recorder system health."""

from homeassistant.components.recorder import get_instance
from homeassistant.setup import async_setup_component

from .common import async_wait_recording_done

from tests.common import get_system_health_info


async def test_recorder_system_health(hass, recorder_mock):
    """Test recorder system health."""
    assert await async_setup_component(hass, "system_health", {})
    await async_wait_recording_done(hass)
    info = await get_system_health_info(hass, "recorder")
    instance = get_instance(hass)
    assert info == {
        "current_recorder_run": instance.run_history.current.start,
        "oldest_recorder_run": instance.run_history.first.start,
    }
