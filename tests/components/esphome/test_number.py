"""Test ESPHome numbers."""

import math
from unittest.mock import Mock, call

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    NumberInfo,
    NumberMode as ESPHomeNumberMode,
    NumberState,
)
import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_generic_number_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic number entity."""
    entity_info = [
        NumberInfo(
            object_id="mynumber",
            key=1,
            name="my number",
            unique_id="my_number",
            max_value=100,
            min_value=0,
            step=1,
            unit_of_measurement="%",
        )
    ]
    states = [NumberState(key=1, state=50)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("number.test_mynumber")
    assert state is not None
    assert state.state == "50"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_mynumber", ATTR_VALUE: 50},
        blocking=True,
    )
    mock_client.number_command.assert_has_calls([call(1, 50)])
    mock_client.number_command.reset_mock()


async def test_generic_number_nan(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic number entity with nan state."""
    entity_info = [
        NumberInfo(
            object_id="mynumber",
            key=1,
            name="my number",
            unique_id="my_number",
            max_value=100,
            min_value=0,
            step=1,
            unit_of_measurement="%",
            mode=ESPHomeNumberMode.SLIDER,
        )
    ]
    states = [NumberState(key=1, state=math.nan)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("number.test_mynumber")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_generic_number_with_unit_of_measurement_as_empty_string(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic number entity with nan state."""
    entity_info = [
        NumberInfo(
            object_id="mynumber",
            key=1,
            name="my number",
            unique_id="my_number",
            max_value=100,
            min_value=0,
            step=1,
            unit_of_measurement="",
            mode=ESPHomeNumberMode.SLIDER,
        )
    ]
    states = [NumberState(key=1, state=42)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("number.test_mynumber")
    assert state is not None
    assert state.state == "42"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes


async def test_generic_number_entity_set_when_disconnected(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
) -> None:
    """Test a generic number entity."""
    entity_info = [
        NumberInfo(
            object_id="mynumber",
            key=1,
            name="my number",
            unique_id="my_number",
            max_value=100,
            min_value=0,
            step=1,
            unit_of_measurement="%",
        )
    ]
    states = [NumberState(key=1, state=50)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )

    mock_client.number_command = Mock(side_effect=APIConnectionError("Not connected"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.test_mynumber", ATTR_VALUE: 20},
            blocking=True,
        )
    mock_client.number_command.reset_mock()
