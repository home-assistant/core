"""Tests for the Bosch SHC button platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from .conftest import motion_detector2_device, setup_integration, smoke_detector_device

from tests.common import MockConfigEntry

ENTITY_ID = "button.smoke_detector_start_self_test"


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


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors2": [motion_detector2_device()]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_reset_tamper_button_press(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Pressing the button resets the tamper condition."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.motion_detectors2[0]

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.motion_detector_reset_tamper"},
        blocking=True,
    )

    device.reset_tampered_state.assert_called_once_with()


@pytest.mark.parametrize(
    "device_buckets",
    [{"motion_detectors2": [motion_detector2_device(supports_tamper_reset=False)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_no_reset_tamper_button_without_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No tamper reset button is created without the LatestTamper service."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("button.motion_detector_reset_tamper") is None
