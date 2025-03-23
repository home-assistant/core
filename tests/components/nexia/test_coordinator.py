"""Test nexia coordinator."""

from homeassistant.components import logger
from homeassistant.components.nexia import NexiaDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .util import async_init_integration


async def test_log_control(hass: HomeAssistant) -> None:
    """Test changing log response."""
    assert await async_setup_component(hass, logger.const.DOMAIN, {"logger": {}}) is True
    config_entry = await async_init_integration(hass)
    coordinator: NexiaDataUpdateCoordinator = config_entry.runtime_data
    assert isinstance(coordinator, NexiaDataUpdateCoordinator) is True
    nexia_home = coordinator.nexia_home

    assert nexia_home.log_response is False

    await hass.services.async_call(
        logger.const.DOMAIN,
        logger.const.SERVICE_SET_LEVEL,
        {"homeassistant.components.nexia": logger.const.LOGSEVERITY_DEBUG},
        blocking=True,
    )
    assert nexia_home.log_response is True

    await hass.services.async_call(
        logger.const.DOMAIN,
        logger.const.SERVICE_SET_LEVEL,
        {"homeassistant.components.nexia": logger.const.LOGSEVERITY_WARNING},
        blocking=True,
    )
    assert nexia_home.log_response is False
