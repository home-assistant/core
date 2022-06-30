"""Common tools used for the Tradfri test suite."""
from homeassistant.components import tradfri

from . import GATEWAY_ID

from tests.common import MockConfigEntry


async def setup_integration(hass):
    """Load the Tradfri integration with a mock gateway."""
    entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            "host": "mock-host",
            "identity": "mock-identity",
            "key": "mock-key",
            "gateway_id": GATEWAY_ID,
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
