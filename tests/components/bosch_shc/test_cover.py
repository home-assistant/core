"""Tests for the Bosch SHC cover platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    Platform,
)
from homeassistant.core import HomeAssistant

from .conftest import (
    micromodule_blinds_device,
    setup_integration,
    shutter_control_device,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the cover platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.COVER]):
        yield


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_controls": [shutter_control_device(device_model="BBL", level=0.75)]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_bbl_shutter_control(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A plain BBL shutter is exposed as a shutter-class cover."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.shutter_controls[0]

    state = hass.states.get("cover.shutter")
    assert state is not None
    assert state.attributes["device_class"] == "shutter"
    assert state.attributes["current_position"] == 75

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.shutter"},
        blocking=True,
    )
    assert device.level == 1.0

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.shutter"},
        blocking=True,
    )
    assert device.level == 0.0

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.shutter", ATTR_POSITION: 42},
        blocking=True,
    )
    assert device.level == pytest.approx(0.42)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.shutter"},
        blocking=True,
    )
    device.stop.assert_called_once()


@pytest.mark.parametrize(
    ("device_buckets", "expected_device_class"),
    [
        pytest.param(
            {
                "micromodule_shutter_controls": [
                    shutter_control_device(device_model="MICROMODULE_SHUTTER")
                ]
            },
            "shutter",
            id="micromodule_shutter",
        ),
        pytest.param(
            {
                "micromodule_shutter_controls": [
                    shutter_control_device(device_model="MICROMODULE_AWNING")
                ]
            },
            "awning",
            id="micromodule_awning",
        ),
    ],
    indirect=["device_buckets"],
)
@pytest.mark.usefixtures("mock_session")
async def test_micromodule_shutter_device_class(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected_device_class: str,
) -> None:
    """A micromodule shutter/awning device (#181407) gets the right device class."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.shutter")
    assert state is not None
    assert state.attributes["device_class"] == expected_device_class


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "micromodule_blinds": [
                micromodule_blinds_device(level=0.6, current_angle=0.25)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_micromodule_blinds_tilt(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Micromodule blinds (#181407) expose tilt controls in addition to lift."""
    await setup_integration(hass, mock_config_entry)
    device = mock_session.device_helper.micromodule_blinds[0]

    state = hass.states.get("cover.blinds")
    assert state is not None
    assert state.attributes["device_class"] == "blind"
    assert state.attributes["current_position"] == 60
    assert state.attributes["current_tilt_position"] == 75

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.blinds"},
        blocking=True,
    )
    assert device.target_angle == 0.0

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.blinds"},
        blocking=True,
    )
    assert device.target_angle == 1.0

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.blinds", ATTR_TILT_POSITION: 30},
        blocking=True,
    )
    assert device.target_angle == pytest.approx(0.7)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.blinds"},
        blocking=True,
    )
    device.stop_blinds.assert_called_once()
