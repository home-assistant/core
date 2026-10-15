"""Test the myStrom light."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pymystrom.exceptions import MyStromConnectionError
import pytest

from homeassistant.components.light import SCAN_INTERVAL
from homeassistant.components.mystrom.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .test_init import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_light_action_raises_when_bulb_unreachable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    service: str,
) -> None:
    """Test the light action reports the failure to the caller."""
    await init_integration(hass, config_entry, 102)
    # The light becomes available after its first poll.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    bulb = config_entry.runtime_data.device
    bulb.set_on = AsyncMock(side_effect=MyStromConnectionError())
    bulb.set_off = AsyncMock(side_effect=MyStromConnectionError())

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            "light",
            service,
            {ATTR_ENTITY_ID: "light.mystrom_device"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "light_action_failed"
