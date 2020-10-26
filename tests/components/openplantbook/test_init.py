"""Test the __init__.py functions."""
from homeassistant import setup
from homeassistant.components.openplantbook.const import DOMAIN

# from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_async_setup_entry(hass):
    """Test async_setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "client_id": "xxxx",
            "secret": "xxxx",
        },
    )
    entry.add_to_hass(hass)
    assert await setup.async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert "API" in hass.data[DOMAIN]
    assert "SPECIES" in hass.data[DOMAIN]

    state = hass.states.get(f"{DOMAIN}.search_result")
    assert state is not None
    assert int(state.state) == 0
