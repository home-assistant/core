"""Tests for the Bosch SHC button platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from .conftest import setup_integration, smoke_detector_device

from tests.common import MockConfigEntry

ENTITY_ID = "button.smoke_detector_test_alarm"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the button platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.mark.parametrize(
    "device_buckets",
    [{"smoke_detectors": [smoke_detector_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_smoke_test_button_press(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Pressing the button requests a smoke detector self-test."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.smoke_detectors[0]

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    device.smoketest_requested.assert_called_once_with()
