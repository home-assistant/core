"""Tests for Srp Energy component Init."""
from homeassistant.components import srp_energy
from homeassistant.const import CONF_ID, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry

MOCK_ENTRY = MockConfigEntry(
    domain=srp_energy.DOMAIN,
    data={
        CONF_NAME: "Test",
        CONF_ID: "1",
        CONF_USERNAME: "abba",
        CONF_PASSWORD: "ana",
    },
)


async def test_setup_with_config(hass):
    """Test that we import the config and setup the integration."""
    config = {
        srp_energy.DOMAIN: {
            CONF_NAME: "Test",
            CONF_ID: "1",
            CONF_USERNAME: "abba",
            CONF_PASSWORD: "ana",
        }
    }
    mock_form = {
        CONF_NAME: "Test",
        CONF_ID: "1",
        CONF_USERNAME: "abba",
        CONF_PASSWORD: "ana",
    }

    # Setup config first
    with patch("homeassistant.components.srp_energy.config_flow.SrpEnergyClient"):
        await hass.config_entries.flow.async_init(
            srp_energy.DOMAIN, context={"source": "user"}, data=mock_form
        )

    with patch("homeassistant.components.srp_energy.SrpEnergyClient"):
        assert await async_setup_component(hass, srp_energy.DOMAIN, config)

    # with patch("speedtest.Speedtest"):
    #     assert await async_setup_component(hass, srp_energy.DOMAIN, config)


# async def test_unload_entry(hass, api):
#     """Test removing transmission client."""
#     entry = MOCK_ENTRY
#     entry.add_to_hass(hass)

#     # with patch.object(
#     #     hass.config_entries, "async_forward_entry_unload", return_value=mock_coro(True)
#     # ) as unload_entry:
#     #     assert await srp_energy.async_setup_entry(hass, entry)

#     assert await srp_energy.async_unload_entry(hass, entry)
#     # assert unload_entry.call_count == 2
#     # assert entry.entry_id not in hass.data[srp_energy.DOMAIN]
