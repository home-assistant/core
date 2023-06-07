"""Test the Anova Switches."""
from unittest.mock import AsyncMock

from anova_wifi import AnovaApi
import pytest

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import async_init_integration

DEVICE_ID = "switch.anova_precision_cooker_circulating"


async def test_turn_on(
    hass: HomeAssistant, anova_api: AnovaApi, anova_precision_cooker: AsyncMock
) -> None:
    """Test turning on an Anova switch."""
    await async_init_integration(hass)
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
    )
    assert anova_precision_cooker.set_mode.call_args_list[0][0][0] == "COOK"


async def test_turn_on_failure(
    hass: HomeAssistant,
    anova_api: AnovaApi,
    anova_precision_cooker_setter_failure: AsyncMock,
) -> None:
    """Test an error when you turn on an Anova switch."""
    with pytest.raises(HomeAssistantError):
        await async_init_integration(hass)
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )


async def test_turn_off(
    hass: HomeAssistant, anova_api: AnovaApi, anova_precision_cooker: AsyncMock
) -> None:
    """Test turning on an Anova switch."""
    await async_init_integration(hass)
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
    )
    assert anova_precision_cooker.set_mode.call_args_list[0][0][0] == "IDLE"


async def test_turn_off_failure(
    hass: HomeAssistant,
    anova_api: AnovaApi,
    anova_precision_cooker_setter_failure: AsyncMock,
) -> None:
    """Test an error when you turn on an Anova switch."""
    with pytest.raises(HomeAssistantError):
        await async_init_integration(hass)
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
