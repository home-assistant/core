from unittest.mock import patch, _patch

from homeassistant.components.imou_life.const import DOMAIN
from homeassistant.core import HomeAssistant
from tests.common import MockConfigEntry

USER_INPUT = {
    "app_id": "test_app_id",
    "app_secret": "test_app_secret",
    "api_url": "openapi-sg.easy4ip.com",
}


def patch_async_setup_entry() -> _patch:
    return patch(
        "homeassistant.components.imou_life.async_setup_entry", return_value=True
    )


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
