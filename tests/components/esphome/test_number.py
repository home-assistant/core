"""Test ESPHome numbers."""

from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    NumberInfo,
    NumberState,
)

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_generic_numeric_entity(
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
    state = hass.states.get("number.test_my_number")
    assert state is not None
    assert state.state == "50"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_my_number", ATTR_VALUE: 50},
        blocking=True,
    )
    mock_client.number_command.assert_has_calls([call(1, 50)])
    mock_client.number_command.reset_mock()
