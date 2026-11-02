"""Tests for Broadlink number entities."""

import asyncio
from typing import Any

import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import get_device

FULL_STATUS = {
    "power": 1,
    "auto_mode": 1,
    "loop_mode": 2,
    "sensor": 0,
    "osv": 42,
    "dif": 2,
    "svh": 35,
    "svl": 5,
    "room_temp_adj": -0.5,
    "fre": 0,
    "poweron": 1,
    "room_temp": 21.5,
    "thermostat_temp": 22.0,
}


@pytest.mark.parametrize(
    ("entity_id", "expected_state", "new_value", "expected_svh", "expected_svl"),
    [
        pytest.param("number.guest_room_minimum_setpoint", "5", 10, 35, 10, id="min"),
        pytest.param("number.guest_room_maximum_setpoint", "35", 30, 30, 5, id="max"),
    ],
)
async def test_setpoint_limits(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    expected_state: str,
    new_value: int,
    expected_svh: int,
    expected_svl: int,
) -> None:
    """Test reading and writing the Hysen setpoint limits."""
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.get_full_status.return_value = FULL_STATUS
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    entry = entity_registry.async_get(entity_id)
    assert entry.entity_category is EntityCategory.CONFIG
    assert hass.states.get(entity_id).state == expected_state

    # The device was switched to manual mode since the last poll.
    mock_setup.api.get_full_status.return_value = {**FULL_STATUS, "auto_mode": 0}

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: new_value},
        blocking=True,
    )

    # The other advanced settings must be sent back as currently on the device,
    # including the mode byte that get_full_status reports as two nibbles.
    mock_setup.api.set_advanced.assert_awaited_once_with(
        loop_mode=0x20,
        sensor=0,
        osv=42,
        dif=2,
        svh=expected_svh,
        svl=expected_svl,
        adj=-0.5,
        fre=0,
        poweron=1,
    )


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        pytest.param("number.guest_room_minimum_setpoint", 36, id="min_above_max"),
        pytest.param("number.guest_room_maximum_setpoint", 19, id="max_below_min"),
    ],
)
async def test_setpoint_limits_inverted(
    hass: HomeAssistant, entity_id: str, value: int
) -> None:
    """Test the minimum setpoint cannot be set above the maximum."""
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.get_full_status.return_value = {**FULL_STATUS, "svl": 20, "svh": 35}
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )

    assert exc_info.value.translation_key == "setpoint_limits_inverted"
    mock_setup.api.set_advanced.assert_not_awaited()


async def test_setpoint_limits_fahrenheit(hass: HomeAssistant) -> None:
    """Test a limit set in Fahrenheit is rounded to the nearest degree Celsius."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.get_full_status.return_value = FULL_STATUS
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    # 73 °F is 22.78 °C.
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.guest_room_maximum_setpoint", ATTR_VALUE: 73},
        blocking=True,
    )

    assert mock_setup.api.set_advanced.await_args.kwargs["svh"] == 23


async def test_setpoint_limits_concurrent(hass: HomeAssistant) -> None:
    """Test concurrent changes to both limits are both kept."""
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.get_full_status.return_value = FULL_STATUS
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    status = dict(FULL_STATUS)

    async def get_full_status() -> dict[str, Any]:
        return dict(status)

    async def set_advanced(**settings: Any) -> None:
        # Let the other request run before the device applies this one.
        await asyncio.sleep(0)
        status.update(svh=settings["svh"], svl=settings["svl"])

    mock_setup.api.get_full_status.side_effect = get_full_status
    mock_setup.api.set_advanced.side_effect = set_advanced

    await asyncio.gather(
        *(
            hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
                blocking=True,
            )
            for entity_id, value in (
                ("number.guest_room_minimum_setpoint", 10),
                ("number.guest_room_maximum_setpoint", 30),
            )
        )
    )

    assert (status["svl"], status["svh"]) == (10, 30)
