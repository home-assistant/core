"""Tests for Vallox fan platform."""

from unittest.mock import call

import pytest
from vallox_websocket_api import MetricData, MetricValue, Profile, ValloxApiException

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    NotValidPresetModeError,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import patch_set_fan_speed, patch_set_profile, patch_set_values

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("metrics", "expected_state"),
    [({"A_CYC_MODE": 0}, "on"), ({"A_CYC_MODE": 5}, "off")],
)
async def test_fan_state(
    metrics: dict[str, MetricValue],
    expected_state: str,
    mock_entry: MockConfigEntry,
    setup_fetch_metric_data_mock,
    hass: HomeAssistant,
) -> None:
    """Test fan on/off state."""

    # Arrange
    fetch_metric_data_mock = setup_fetch_metric_data_mock(metrics=metrics)

    # Act
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # Assert
    fetch_metric_data_mock.assert_called_once()
    sensor = hass.states.get("fan.vallox")
    assert sensor
    assert sensor.state == expected_state


@pytest.mark.parametrize(
    ("vallox_profile", "expected_preset"),
    [
        (Profile.HOME, "Home"),
        (Profile.AWAY, "Away"),
        (Profile.BOOST, "Boost"),
        (Profile.FIREPLACE, "Fireplace"),
    ],
)
async def test_fan_profile(
    vallox_profile: Profile,
    expected_preset: str,
    mock_entry: MockConfigEntry,
    setup_fetch_metric_data_mock,
    hass: HomeAssistant,
) -> None:
    """Test fan profile."""

    # Arrange
    class MockMetricData(MetricData):
        @property
        def profile(self):
            return vallox_profile

    setup_fetch_metric_data_mock(metric_data_class=MockMetricData)

    # Act
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("fan.vallox")
    assert sensor
    assert sensor.attributes["preset_mode"] == expected_preset


@pytest.mark.parametrize(
    ("service", "initial_metrics", "expected_called_with"),
    [
        (SERVICE_TURN_ON, {"A_CYC_MODE": 5}, {"A_CYC_MODE": 0}),
        (SERVICE_TURN_OFF, {"A_CYC_MODE": 0}, {"A_CYC_MODE": 5}),
    ],
)
async def test_turn_on_off(
    service: str,
    initial_metrics: dict[str, MetricValue],
    expected_called_with: dict[str, MetricValue],
    mock_entry: MockConfigEntry,
    setup_fetch_metric_data_mock,
    hass: HomeAssistant,
) -> None:
    """Test turn on/off."""
    setup_fetch_metric_data_mock(metrics=initial_metrics)

    with patch_set_values() as set_values:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            service_data={ATTR_ENTITY_ID: "fan.vallox"},
            blocking=True,
        )
        set_values.assert_called_once_with(expected_called_with)


@pytest.mark.parametrize(
    ("initial_metrics", "expected_call_args_list"),
    [
        (
            {"A_CYC_MODE": 5},
            [
                call({"A_CYC_MODE": 0}),
                call({"A_CYC_AWAY_SPEED_SETTING": 15}),
            ],
        ),
        (
            {"A_CYC_MODE": 0},
            [
                call({"A_CYC_AWAY_SPEED_SETTING": 15}),
            ],
        ),
    ],
)
async def test_turn_on_with_parameters(
    initial_metrics: dict[str, MetricValue],
    expected_call_args_list: list[tuple],
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
    setup_fetch_metric_data_mock,
) -> None:
    """Test turn on/off."""

    setup_fetch_metric_data_mock(metrics=initial_metrics)

    with patch_set_values() as set_values, patch_set_profile() as set_profile:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            service_data={
                ATTR_ENTITY_ID: "fan.vallox",
                ATTR_PERCENTAGE: "15",
                ATTR_PRESET_MODE: "Away",
            },
            blocking=True,
        )
        set_profile.assert_called_once_with(Profile.AWAY)
        assert set_values.call_args_list == expected_call_args_list


@pytest.mark.parametrize(
    ("preset", "initial_profile", "expected_call_args_list"),
    [
        ("Home", Profile.AWAY, [call(Profile.HOME)]),
        ("Away", Profile.HOME, [call(Profile.AWAY)]),
        ("Boost", Profile.HOME, [call(Profile.BOOST)]),
        ("Fireplace", Profile.HOME, [call(Profile.FIREPLACE)]),
        ("Home", Profile.HOME, []),  # No change
    ],
)
async def test_set_preset_mode(
    preset: str,
    initial_profile: Profile,
    expected_call_args_list: list[tuple],
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
    setup_fetch_metric_data_mock,
) -> None:
    """Test set preset mode."""

    class MockMetricData(MetricData):
        @property
        def profile(self):
            return initial_profile

    setup_fetch_metric_data_mock(metric_data_class=MockMetricData)

    with patch_set_profile() as set_profile:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            service_data={ATTR_ENTITY_ID: "fan.vallox", ATTR_PRESET_MODE: preset},
            blocking=True,
        )
        assert set_profile.call_args_list == expected_call_args_list


async def test_set_invalid_preset_mode(
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test set preset mode."""
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(NotValidPresetModeError) as exc:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            service_data={
                ATTR_ENTITY_ID: "fan.vallox",
                ATTR_PRESET_MODE: "Invalid",
            },
            blocking=True,
        )
    assert exc.value.translation_key == "not_valid_preset_mode"


async def test_set_preset_mode_exception(
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test set preset mode."""
    with patch_set_profile() as set_profile:
        set_profile.side_effect = ValloxApiException("Fake exception")
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                FAN_DOMAIN,
                SERVICE_SET_PRESET_MODE,
                service_data={ATTR_ENTITY_ID: "fan.vallox", ATTR_PRESET_MODE: "Away"},
                blocking=True,
            )


@pytest.mark.parametrize(
    (
        "initial_profile",
        "percentage",
        "expected_set_fan_speed_call",
        "expected_set_values_call",
    ),
    [
        (Profile.HOME, 40, [call(Profile.HOME, 40)], []),
        (Profile.AWAY, 30, [call(Profile.AWAY, 30)], []),
        (Profile.BOOST, 60, [call(Profile.BOOST, 60)], []),
        (Profile.HOME, 0, [], [call({"A_CYC_MODE": 5})]),  # Turn off
    ],
)
async def test_set_fan_speed(
    initial_profile: Profile,
    percentage: int,
    expected_set_fan_speed_call: list[tuple],
    expected_set_values_call: list[tuple],
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
    setup_fetch_metric_data_mock,
) -> None:
    """Test set fan speed percentage."""

    class MockMetricData(MetricData):
        @property
        def profile(self):
            return initial_profile

    setup_fetch_metric_data_mock(
        metrics={"A_CYC_MODE": 0}, metric_data_class=MockMetricData
    )

    with patch_set_fan_speed() as set_fan_speed, patch_set_values() as set_values:
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            service_data={ATTR_ENTITY_ID: "fan.vallox", ATTR_PERCENTAGE: percentage},
            blocking=True,
        )
        assert set_fan_speed.call_args_list == expected_set_fan_speed_call
        assert set_values.call_args_list == expected_set_values_call


async def test_set_fan_speed_exception(
    mock_entry: MockConfigEntry, hass: HomeAssistant, setup_fetch_metric_data_mock
) -> None:
    """Test set fan speed percentage."""
    setup_fetch_metric_data_mock(
        metrics={"A_CYC_MODE": 0, "A_CYC_HOME_SPEED_SETTING": 30}
    )

    with patch_set_values() as set_values:
        set_values.side_effect = ValloxApiException("Fake failure")
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                FAN_DOMAIN,
                SERVICE_SET_PERCENTAGE,
                service_data={ATTR_ENTITY_ID: "fan.vallox", ATTR_PERCENTAGE: 5},
                blocking=True,
            )
