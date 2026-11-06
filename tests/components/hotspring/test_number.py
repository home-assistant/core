"""Tests for the Hot Spring number platform."""

from unittest.mock import MagicMock

from hotspring import HotSpringConnectionError, HotSpringError, Spa, TemperatureUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

ENTITY_ID = "number.connectedspa_ddeeff_target_temperature"
SALT_OUTPUT_LEVEL_ENTITY_ID = "number.connectedspa_ddeeff_salt_output_level"


@pytest.mark.usefixtures("mock_hotspring")
@pytest.mark.parametrize(
    "cartridge_installed",
    [
        pytest.param(True, id="with_cartridge"),
        pytest.param(False, id="without_cartridge"),
    ],
)
async def test_number_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device_fixture: Spa,
    cartridge_installed: bool,
) -> None:
    """Test the number entity state with and without a salt cartridge."""
    device_fixture.water_care.cartridge_installed = cartridge_installed
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_set_target_temperature(
    hass: HomeAssistant,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test setting target temperature."""
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "40.0"

    def set_temp_mock(value: float) -> None:
        device_fixture.heater.set_temperature = value

    mock_hotspring.set_temperature.side_effect = set_temp_mock

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 38,
        },
        blocking=True,
    )

    mock_hotspring.set_temperature.assert_called_once_with(100.0)
    mock_hotspring.update.assert_called_once()
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "37.8"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("exception", "match"),
    [
        (
            HotSpringConnectionError,
            "An error occurred while communicating with the Hot Spring API",
        ),
        (HotSpringError, "Invalid response received from the Hot Spring API"),
    ],
)
async def test_set_target_temperature_error(
    hass: HomeAssistant,
    mock_hotspring: MagicMock,
    exception: type[Exception],
    match: str,
) -> None:
    """Test exception handling when setting target temperature."""
    mock_hotspring.set_temperature.side_effect = exception

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_VALUE: 38,
            },
            blocking=True,
        )


async def test_set_target_temperature_celsius(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting target temperature when the spa is configured in Celsius."""
    device_fixture.heater.temperature_unit = TemperatureUnit.CELSIUS
    device_fixture.heater.set_temperature = 38.5

    def set_temp_mock(value: float) -> None:
        device_fixture.heater.set_temperature = value

    mock_hotspring.set_temperature.side_effect = set_temp_mock

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    assert hass.states.get(ENTITY_ID) == snapshot

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_VALUE: 37.5,
        },
        blocking=True,
    )

    mock_hotspring.set_temperature.assert_called_once_with(37.5)
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "37.5"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("value", "expected_level"),
    [
        pytest.param(0.0, 0, id="min"),
        pytest.param(7.0, 7, id="mid"),
        pytest.param(10.0, 10, id="max"),
    ],
)
async def test_set_salt_output_level(
    hass: HomeAssistant,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
    value: float,
    expected_level: int,
) -> None:
    """Test setting the salt output level."""
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"

    def set_level_mock(level: int) -> None:
        device_fixture.water_care.level = level

    mock_hotspring.set_water_care_level.side_effect = set_level_mock

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: SALT_OUTPUT_LEVEL_ENTITY_ID,
            ATTR_VALUE: value,
        },
        blocking=True,
    )

    mock_hotspring.set_water_care_level.assert_called_once_with(expected_level)
    mock_hotspring.update.assert_called_once()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == str(expected_level)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("exception", "match"),
    [
        (
            HotSpringConnectionError,
            "An error occurred while communicating with the Hot Spring API",
        ),
        (HotSpringError, "Invalid response received from the Hot Spring API"),
    ],
)
async def test_set_salt_output_level_error(
    hass: HomeAssistant,
    mock_hotspring: MagicMock,
    exception: type[Exception],
    match: str,
) -> None:
    """Test exception handling when setting the salt output level."""
    mock_hotspring.set_water_care_level.side_effect = exception

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: SALT_OUTPUT_LEVEL_ENTITY_ID,
                ATTR_VALUE: 3.0,
            },
            blocking=True,
        )

    mock_hotspring.update.assert_called_once()
    assert (state := hass.states.get(SALT_OUTPUT_LEVEL_ENTITY_ID))
    assert state.state == "2"
