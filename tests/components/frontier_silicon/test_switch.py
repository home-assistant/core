"""Test the Frontier Silicon switch entity."""

from unittest.mock import AsyncMock

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

DST_SWITCH_ENTITY_ID = "switch.name_of_the_device_daylight_saving_time"


async def test_dst_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_afsapi: AsyncMock,
) -> None:
    """Test turn_on and turn_off for DST switch."""

    # Set up integration
    await setup_integration(hass, config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DST_SWITCH_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_afsapi.set_dst.assert_awaited_with(True)
    mock_afsapi.set_dst.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: DST_SWITCH_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_afsapi.set_dst.assert_awaited_with(False)
    mock_afsapi.set_dst.reset_mock()
