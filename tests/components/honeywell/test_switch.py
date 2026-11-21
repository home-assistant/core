"""Tests for Honeywell switch component."""

from unittest.mock import MagicMock

from aiohttp import ClientConnectionError
from aiosomecomfort.exceptions import SomeComfortError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import init_integration


async def test_emheat_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device: MagicMock,
) -> None:
    """Test emergency heat switch."""

    await init_integration(hass, config_entry)
    entity_id = f"switch.{device.name}_emergency_heat"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("emheat")

    device.set_system_mode.reset_mock()

    device.system_mode = "emheat"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("off")

    device.set_system_mode.reset_mock()
    device.system_mode = "heat"
    device.set_system_mode.side_effect = SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: entity_id},
            blocking=True,
        )
    device.set_system_mode.assert_called_once_with("emheat")

    device.set_system_mode.reset_mock()
    device.system_mode = "emheat"
    device.set_system_mode.side_effect = SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_OFF,
            {TargetKey.ENTITY_ID: entity_id},
            blocking=True,
        )
    device.set_system_mode.assert_called_once_with("off")


@pytest.mark.parametrize("error", [TimeoutError, ClientConnectionError])
@pytest.mark.parametrize(
    ("system_mode", "service", "translation_key"),
    [
        ("heat", SwitchService.TURN_ON, "switch_failed_on"),
        ("emheat", SwitchService.TURN_OFF, "switch_failed_off"),
    ],
)
async def test_emheat_switch_connection_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device: MagicMock,
    system_mode: str,
    service: SwitchService,
    translation_key: str,
    error: type[Exception],
) -> None:
    """Test timeouts and connection errors raise HomeAssistantError."""
    await init_integration(hass, config_entry)
    entity_id = f"switch.{device.name}_emergency_heat"
    device.system_mode = system_mode
    device.set_system_mode.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {TargetKey.ENTITY_ID: entity_id},
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key
    assert isinstance(exc_info.value.__cause__, error)
