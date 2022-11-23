"""Tests for Vallox fan platform."""
import pytest
from vallox_websocket_api import PROFILE

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from .conftest import patch_metrics, patch_metrics_set, patch_profile, patch_profile_set

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "metrics, expected_state", [({"A_CYC_MODE": 0}, "on"), ({"A_CYC_MODE": 5}, "off")]
)
async def test_fan_state(
    metrics: dict[str, int],
    expected_state: str,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test fan on/off state."""

    # Act
    with patch_metrics(metrics=metrics):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("fan.vallox")
    assert sensor
    assert sensor.state == expected_state


@pytest.mark.parametrize(
    "profile, expected_preset",
    [
        (PROFILE.HOME, "Home"),
        (PROFILE.AWAY, "Away"),
        (PROFILE.BOOST, "Boost"),
        (PROFILE.FIREPLACE, "Fireplace"),
    ],
)
async def test_fan_profile(
    profile: PROFILE,
    expected_preset: str,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test fan profile."""

    # Act
    with patch_profile(profile), patch_metrics({}):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("fan.vallox")
    assert sensor
    assert sensor.attributes["preset_mode"] == expected_preset


@pytest.mark.parametrize(
    "service, initial_metrics, expected_called_with",
    [
        (SERVICE_TURN_ON, {"A_CYC_MODE": 5}, {"A_CYC_MODE": 0}),
        (SERVICE_TURN_OFF, {"A_CYC_MODE": 0}, {"A_CYC_MODE": 5}),
    ],
)
async def test_turn_on_off(
    service: str,
    initial_metrics: dict[str, int],
    expected_called_with: dict[str, int],
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test turn on/off."""
    with patch_metrics(metrics=initial_metrics), patch_metrics_set() as metrics_set:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            service_data={ATTR_ENTITY_ID: "fan.vallox"},
            blocking=True,
        )
        metrics_set.assert_called_once_with(expected_called_with)


@pytest.mark.parametrize(
    "preset, initial_profile, expected_profile",
    [
        ("Home", PROFILE.AWAY, PROFILE.HOME),
        ("Away", PROFILE.HOME, PROFILE.AWAY),
        ("Boost", PROFILE.HOME, PROFILE.BOOST),
        ("Fireplace", PROFILE.HOME, PROFILE.FIREPLACE),
    ],
)
async def test_set_preset_mode(
    preset: str,
    initial_profile: PROFILE,
    expected_profile: PROFILE,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test set preset mode."""
    with patch_metrics(metrics={}), patch_profile(
        initial_profile
    ), patch_profile_set() as profile_set:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            service_data={ATTR_ENTITY_ID: "fan.vallox", ATTR_PRESET_MODE: preset},
            blocking=True,
        )
        profile_set.assert_called_once_with(expected_profile)


@pytest.mark.parametrize(
    "profile, percentage, expected_called_with",
    [
        (PROFILE.HOME, 40, {"A_CYC_HOME_SPEED_SETTING": 40}),
        (PROFILE.AWAY, 30, {"A_CYC_AWAY_SPEED_SETTING": 30}),
        (PROFILE.BOOST, 60, {"A_CYC_BOOST_SPEED_SETTING": 60}),
    ],
)
async def test_set_fan_speed(
    profile: PROFILE,
    percentage: int,
    expected_called_with: dict[str, int],
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test set fan speed percentage."""
    with patch_profile(profile), patch_metrics_set() as metrics_set:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            service_data={ATTR_ENTITY_ID: "fan.vallox", ATTR_PERCENTAGE: percentage},
            blocking=True,
        )
        metrics_set.assert_called_once_with(expected_called_with)
