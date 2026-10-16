"""Test the myStrom switch."""

from unittest.mock import AsyncMock

from pymystrom.exceptions import MyStromConnectionError
import pytest

from homeassistant.components.mystrom.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .test_init import init_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_switch_action_raises_when_plug_unreachable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test the switch action reports the failure to the caller."""
    await init_integration(hass, config_entry, 106)

    device = config_entry.runtime_data.device
    device._state["on"] = True
    device.turn_on = AsyncMock(side_effect=MyStromConnectionError())
    device.turn_off = AsyncMock(side_effect=MyStromConnectionError())

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            "switch",
            service,
            {ATTR_ENTITY_ID: "switch.mystrom_device"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "switch_action_failed"
