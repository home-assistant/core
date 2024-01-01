"""Add tests for Tedee components."""
from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


async def prepare_webhook_setup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Prepare webhooks are registered by waiting a second."""
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
