"""Test Dynalite __init__."""


from asynctest import call, patch

from homeassistant.components import dynalite
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_empty_config(hass):
    """Test with an empty config."""
    assert await async_setup_component(hass, dynalite.DOMAIN, {}) is True
    assert len(hass.config_entries.flow.async_progress()) == 0
    assert len(hass.config_entries.async_entries(dynalite.DOMAIN)) == 0


async def test_async_setup(hass):
    """Test a successful setup."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        assert await async_setup_component(
            hass,
            dynalite.DOMAIN,
            {
                dynalite.DOMAIN: {
                    dynalite.CONF_BRIDGES: [
                        {
                            dynalite.CONF_HOST: host,
                            dynalite.CONF_AREA: {"1": {dynalite.CONF_NAME: "Name"}},
                        }
                    ]
                }
            },
        )
        await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(dynalite.DOMAIN)) == 1


async def test_async_setup_bad_config2(hass):
    """Test a successful with bad config on numbers."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        assert not await async_setup_component(
            hass,
            dynalite.DOMAIN,
            {
                dynalite.DOMAIN: {
                    dynalite.CONF_BRIDGES: [
                        {
                            dynalite.CONF_HOST: host,
                            dynalite.CONF_AREA: {"WRONG": {dynalite.CONF_NAME: "Name"}},
                        }
                    ]
                }
            },
        )
        await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(dynalite.DOMAIN)) == 0


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    host = "1.2.3.4"
    entry = MockConfigEntry(domain=dynalite.DOMAIN, data={dynalite.CONF_HOST: host})
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(dynalite.DOMAIN)) == 1
    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_unload:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_unload.call_count == len(dynalite.ENTITY_PLATFORMS)
        expected_calls = [
            call(entry, platform) for platform in dynalite.ENTITY_PLATFORMS
        ]
        for cur_call in mock_unload.mock_calls:
            assert cur_call in expected_calls
