"""Test for the switch platform entity of the foscam component."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.foscam.const import DOMAIN
from homeassistant.components.foscam.switch import (
    handle_car_Detect_turn_off,
    handle_car_Detect_turn_on,
    handle_human_Detect_turn_off,
    handle_human_Detect_turn_on,
    handle_pet_Detect_turn_off,
    handle_pet_Detect_turn_on,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_mock_foscam_camera
from .const import ENTRY_ID, VALID_CONFIG

from tests.common import MockConfigEntry, snapshot_platform

TEST_CASES = [
    (handle_pet_Detect_turn_on, "petEnable", "1"),
    (handle_pet_Detect_turn_off, "petEnable", "0"),
    (handle_car_Detect_turn_on, "carEnable", "1"),
    (handle_car_Detect_turn_off, "carEnable", "0"),
    (handle_human_Detect_turn_on, "humanEnable", "1"),
    (handle_human_Detect_turn_off, "humanEnable", "0"),
]


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that coordinator returns the data we expect after the first refresh."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG, entry_id=ENTRY_ID)
    entry.add_to_hass(hass)

    with (
        # Mock a valid camera instance"
        patch("homeassistant.components.foscam.FoscamCamera") as mock_foscam_camera,
        patch("homeassistant.components.foscam.PLATFORMS", [Platform.SWITCH]),
    ):
        setup_mock_foscam_camera(mock_foscam_camera)
        assert await hass.config_entries.async_setup(entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(("func", "expected_key", "expected_value"), TEST_CASES)
def test_detection_functions(func, expected_key, expected_value) -> None:
    """Test detection toggle functions with mocked session."""

    mock_session = MagicMock()

    func(mock_session)

    mock_session.set_motion_detect_config.assert_called_once()
    called_args = mock_session.set_motion_detect_config.call_args
    config_dict = called_args[0][0]

    assert config_dict["isEnable"] == 1
    assert config_dict["sensitivity"] == 3
    assert config_dict["triggerInterval"] == 15

    for i in range(7):
        assert config_dict[f"schedule{i}"] == 281474976710655
    for i in range(10):
        assert config_dict[f"area{i}"] == 1023

    assert config_dict[expected_key] == expected_value
