"""Tests for the TechnoVE number platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion
from technove import TechnoVEConnectionError, TechnoVEError

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_technove")
async def test_numbers(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation and values of the TechnoVE numbers."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method", "called_with_value"),
    [
        (
            "number.technove_station_maximum_current",
            "set_max_current",
            {"max_current": 10},
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_number_expected_value(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    entity_id: str,
    method: str,
    called_with_value: dict[str, bool | int],
) -> None:
    """Test set value services with valid values."""
    state = hass.states.get(entity_id)
    method_mock = getattr(mock_technove, method)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_VALUE: called_with_value["max_current"]},
        blocking=True,
    )

    assert method_mock.call_count == 1
    method_mock.assert_called_with(**called_with_value)


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        (
            "number.technove_station_maximum_current",
            1,
        ),
        (
            "number.technove_station_maximum_current",
            1000,
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_number_out_of_bound(
    hass: HomeAssistant,
    entity_id: str,
    value: float,
) -> None:
    """Test set value services with out of bound values."""
    state = hass.states.get(entity_id)

    with pytest.raises(ServiceValidationError, match="is outside valid range"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_VALUE: value},
            blocking=True,
        )

    assert (state := hass.states.get(state.entity_id))
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_set_max_current_sharing_mode(
    hass: HomeAssistant,
    mock_technove: MagicMock,
) -> None:
    """Test failure to set the max current when the station is in sharing mode."""
    entity_id = "number.technove_station_maximum_current"
    state = hass.states.get(entity_id)

    # Enable power sharing mode
    device = mock_technove.update.return_value
    device.info.in_sharing_mode = True

    with pytest.raises(
        ServiceValidationError,
        match="power sharing mode is enabled",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_VALUE: 10,
            },
            blocking=True,
        )

    assert (state := hass.states.get(state.entity_id))
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        (
            "number.technove_station_maximum_current",
            "set_max_current",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_invalid_response(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    entity_id: str,
    method: str,
) -> None:
    """Test invalid response, not becoming unavailable."""
    state = hass.states.get(entity_id)
    method_mock = getattr(mock_technove, method)

    method_mock.side_effect = TechnoVEError
    with pytest.raises(HomeAssistantError, match="Invalid response from TechnoVE API"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_VALUE: 10},
            blocking=True,
        )

    assert method_mock.call_count == 1
    assert (state := hass.states.get(state.entity_id))
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        (
            "number.technove_station_maximum_current",
            "set_max_current",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_connection_error(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    entity_id: str,
    method: str,
) -> None:
    """Test connection error, leading to becoming unavailable."""
    state = hass.states.get(entity_id)
    method_mock = getattr(mock_technove, method)

    method_mock.side_effect = TechnoVEConnectionError
    with pytest.raises(
        HomeAssistantError, match="Error communicating with TechnoVE API"
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_VALUE: 10},
            blocking=True,
        )

    assert method_mock.call_count == 1
    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_UNAVAILABLE
