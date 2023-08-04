"""Test the OSC (Open Sound Control) backup platform."""
from homeassistant.components.osc.backup import (
    async_post_backup,
    async_pre_backup,
)
from homeassistant.core import HomeAssistant


async def test_async_post_backup(hass: HomeAssistant) -> None:
    """Verify async_post_backup."""
    # TODO: verify that the async_post_backup function executes as expected
    assert await async_post_backup(hass)


async def test_async_pre_backup(hass: HomeAssistant) -> None:
    """Verify async_pre_backup."""
    # TODO: verify that the async_pre_backup function executes as expected
    assert await async_pre_backup(hass)
