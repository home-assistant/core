"""Test the Honeywell humidity domain."""

from unittest.mock import MagicMock

from homeassistant.components.humidifier import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_humidifier(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test the setup of the climate entities when there are no additional options available."""
    device.has_humidifier = True
    await init_integration(hass, config_entry)
    entity_id = f"humidifier.{device.name}_humidifier"
    assert hass.states.get(f"humidifier.{device.name}_dehumidifier") is None
    state = hass.states.get(entity_id)
    assert state
    attributes = state.attributes
    assert attributes[ATTR_MAX_HUMIDITY] == 60
    assert attributes[ATTR_MIN_HUMIDITY] == 10
    assert attributes[ATTR_CURRENT_HUMIDITY] == 50
    assert attributes[ATTR_HUMIDITY] == 20

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_humidifier_auto.assert_called_once()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_humidifier_off.assert_called_once()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: entity_id, ATTR_HUMIDITY: 40},
        blocking=True,
    )
    device.set_humidifier_setpoint.assert_called_once_with(40)


async def test_dehumidifier(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test the setup of the climate entities when there are no additional options available."""
    device.has_dehumidifier = True
    await init_integration(hass, config_entry)
    entity_id = f"humidifier.{device.name}_dehumidifier"
    assert hass.states.get(f"humidifier.{device.name}_humidifier") is None
    state = hass.states.get(entity_id)
    assert state
    attributes = state.attributes
    assert attributes[ATTR_MAX_HUMIDITY] == 55
    assert attributes[ATTR_MIN_HUMIDITY] == 15
    assert attributes[ATTR_CURRENT_HUMIDITY] == 50
    assert attributes[ATTR_HUMIDITY] == 30

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_dehumidifier_auto.assert_called_once()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_dehumidifier_off.assert_called_once()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: entity_id, ATTR_HUMIDITY: 40},
        blocking=True,
    )
    device.set_dehumidifier_setpoint.assert_called_once_with(40)
