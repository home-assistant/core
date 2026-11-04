"""Test the services for the Flo by Moen integration."""

from aioflo.location import SYSTEM_MODE_HOME
from probatio.error import MultipleInvalid
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.flo.const import DOMAIN
from homeassistant.components.flo.services import FloService, FloServiceArgument
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant

SWITCH_ENTITY_ID = "switch.smart_water_shutoff_shutoff_valve"


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_services(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test Flo services."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 8

    await hass.services.async_call(
        DOMAIN,
        FloService.RUN_HEALTH_TEST,
        {CommonServiceArgument.ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 9

    await hass.services.async_call(
        DOMAIN,
        FloService.SET_AWAY_MODE,
        {CommonServiceArgument.ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 10

    await hass.services.async_call(
        DOMAIN,
        FloService.SET_HOME_MODE,
        {CommonServiceArgument.ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 11

    await hass.services.async_call(
        DOMAIN,
        FloService.SET_SLEEP_MODE,
        {
            CommonServiceArgument.ENTITY_ID: SWITCH_ENTITY_ID,
            FloServiceArgument.REVERT_TO_MODE: SYSTEM_MODE_HOME,
            FloServiceArgument.SLEEP_MINUTES: 120,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 12

    # test calling with a string value to ensure it is converted to int
    await hass.services.async_call(
        DOMAIN,
        FloService.SET_SLEEP_MODE,
        {
            CommonServiceArgument.ENTITY_ID: SWITCH_ENTITY_ID,
            FloServiceArgument.REVERT_TO_MODE: SYSTEM_MODE_HOME,
            FloServiceArgument.SLEEP_MINUTES: "120",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 13

    # test calling with a non string -> int value and ensure exception is thrown
    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            FloService.SET_SLEEP_MODE,
            {
                CommonServiceArgument.ENTITY_ID: SWITCH_ENTITY_ID,
                FloServiceArgument.REVERT_TO_MODE: SYSTEM_MODE_HOME,
                FloServiceArgument.SLEEP_MINUTES: "test",
            },
            blocking=True,
        )
    assert aioclient_mock.call_count == 13
