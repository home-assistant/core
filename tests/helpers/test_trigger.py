"""The tests for the trigger helper."""
from unittest.mock import MagicMock, call, patch

import pytest
import voluptuous as vol

from homeassistant.helpers.trigger import (
    _async_get_trigger_platform,
    async_validate_trigger_config,
)


async def test_bad_trigger_platform(hass):
    """Test bad trigger platform."""
    with pytest.raises(vol.Invalid) as ex:
        await async_validate_trigger_config(hass, [{"platform": "not_a_platform"}])
    assert "Invalid platform 'not_a_platform' specified" in str(ex)


async def test_trigger_subtype(hass):
    """Test trigger subtypes."""
    with patch(
        "homeassistant.helpers.trigger.async_get_integration", return_value=MagicMock()
    ) as integration_mock:
        await _async_get_trigger_platform(hass, {"platform": "test.subtype"})
        assert integration_mock.call_args == call(hass, "test")
