"""Tests for the component init file."""
import pytest

from homeassistant.components import is_on
from homeassistant.core import HomeAssistant


def test_is_on_reports_error(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
):
    """Test is_on reports error."""
    is_on(hass, "light.kitchen")

    assert (
        "Detected code that uses homeassistant.components.is_on. "
        "This is deprecated and will stop working in"
    ) in caplog.text
