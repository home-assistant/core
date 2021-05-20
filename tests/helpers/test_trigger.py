"""The tests for the trigger helper."""
import pytest
import voluptuous as vol

from homeassistant.helpers.trigger import async_validate_trigger_config


async def test_bad_trigger_platform(hass):
    """Test bad trigger platform."""
    with pytest.raises(vol.Invalid) as ex:
        await async_validate_trigger_config(hass, [{"platform": "not_a_platform"}])
    assert "Invalid platform 'not_a_platform' specified" in str(ex)
