"""Tests for the Hot Spring number platform."""

from unittest.mock import MagicMock

from hotspring import HotSpringConnectionError, HotSpringError, Spa
import pytest
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

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "number.connectedspa_ddeeff_target_temperature"


async def test_number_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the number entity state."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_target_temperature(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_hotspring: MagicMock,
    device_fixture: Spa,
) -> None:
    """Test setting target temperature."""
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "40.0"

    def set_temp_mock(value: int) -> None:
        device_fixture.heater.set_temperature = float(value)

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

    mock_hotspring.set_temperature.assert_called_once_with(100)
    mock_hotspring.update.assert_called_once()
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "37.8"


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
    init_integration: MockConfigEntry,
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
