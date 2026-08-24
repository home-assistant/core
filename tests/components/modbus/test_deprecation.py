"""Test the deprecation of get_hub."""

import pytest

from homeassistant.components.modbus import get_hub
from homeassistant.components.modbus.modbus import DATA_MODBUS_HUBS
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize("integration_frame_path", ["homeassistant/components/flexit"])
@pytest.mark.usefixtures("mock_integration_frame")
async def test_a_core_integration_is_not_warned(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Flexit is the one caller in core, and the user cannot change it."""
    hub = object()
    hass.data[DATA_MODBUS_HUBS] = {"hub": hub}

    assert get_hub(hass, "hub") is hub

    assert "deprecated" not in caplog.text


@pytest.mark.parametrize("integration_frame_path", ["custom_components/my_integration"])
@pytest.mark.usefixtures("mock_integration_frame")
async def test_a_custom_integration_is_warned(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Anything outside core has a config flow of its own to collect details in."""
    hub = object()
    hass.data[DATA_MODBUS_HUBS] = {"hub": hub}

    assert get_hub(hass, "hub") is hub

    assert "deprecated" in caplog.text
    assert "async_get_unit" in caplog.text
    assert "my_integration" in caplog.text
