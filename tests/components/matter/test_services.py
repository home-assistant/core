"""Test Matter services."""

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
import pytest
from voluptuous import MultipleInvalid

from homeassistant.components.matter.services import (
    ATTR_DURATION,
    ATTR_EMERGENCY_BOOST,
    ATTR_TEMPORARY_SETPOINT,
    SERVICE_WATER_HEATER_BOOST,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater_boost_service_basic(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the water_heater_boost service with basic parameters."""
    # Call the service with required parameters only
    await hass.services.async_call(
        "matter",
        SERVICE_WATER_HEATER_BOOST,
        {
            ATTR_ENTITY_ID: "water_heater.water_heater",
            ATTR_DURATION: 3600,
        },
        blocking=True,
    )

    # Verify the service was called
    assert matter_client.send_device_command.call_count >= 1


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater_boost_service_with_options(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the water_heater_boost service with all optional parameters."""
    # Call the service with all parameters
    await hass.services.async_call(
        "matter",
        SERVICE_WATER_HEATER_BOOST,
        {
            ATTR_ENTITY_ID: "water_heater.water_heater",
            ATTR_DURATION: 1800,
            ATTR_EMERGENCY_BOOST: True,
            ATTR_TEMPORARY_SETPOINT: 55,
        },
        blocking=True,
    )

    # Verify the service was called
    assert matter_client.send_device_command.call_count >= 1


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater_boost_service_invalid_duration(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the water_heater_boost service with invalid duration."""
    # Test with duration below minimum (1)
    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            "matter",
            SERVICE_WATER_HEATER_BOOST,
            {
                ATTR_ENTITY_ID: "water_heater.water_heater",
                ATTR_DURATION: 0,
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater_boost_service_invalid_temperature_low(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the water_heater_boost service with temperature below minimum."""
    # Test with temporary_setpoint below minimum (30)
    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            "matter",
            SERVICE_WATER_HEATER_BOOST,
            {
                ATTR_ENTITY_ID: "water_heater.water_heater",
                ATTR_DURATION: 3600,
                ATTR_TEMPORARY_SETPOINT: 29,
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater_boost_service_invalid_temperature_high(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the water_heater_boost service with temperature above maximum."""
    # Test with temporary_setpoint above maximum (65)
    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            "matter",
            SERVICE_WATER_HEATER_BOOST,
            {
                ATTR_ENTITY_ID: "water_heater.water_heater",
                ATTR_DURATION: 3600,
                ATTR_TEMPORARY_SETPOINT: 66,
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater_boost_service_emergency_boost_false(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the water_heater_boost service with emergency_boost set to False."""
    # Call the service with emergency_boost=False
    await hass.services.async_call(
        "matter",
        SERVICE_WATER_HEATER_BOOST,
        {
            ATTR_ENTITY_ID: "water_heater.water_heater",
            ATTR_DURATION: 3600,
            ATTR_EMERGENCY_BOOST: False,
        },
        blocking=True,
    )

    # Verify the service was called
    assert matter_client.send_device_command.call_count >= 1
