"""Test Dynalite __init__."""


from asynctest import patch

from homeassistant.components import dynalite
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_empty_config(hass):
    """Test with an empty config."""
    assert await async_setup_component(hass, dynalite.DOMAIN, {}) is True
    assert len(hass.config_entries.flow.async_progress()) == 0
    assert len(hass.data[dynalite.DOMAIN]) == 0


async def test_async_setup(hass):
    """Test a successful setup."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.available", True
    ):
        assert await async_setup_component(
            hass,
            dynalite.DOMAIN,
            {
                dynalite.DOMAIN: {
                    dynalite.CONF_BRIDGES: [
                        {
                            dynalite.CONF_HOST: host,
                            dynalite.CONF_AREA: {
                                "1": {
                                    dynalite.CONF_NAME: "Name",
                                    dynalite.CONF_TEMPLATE: "room",
                                    dynalite.CONF_ROOM_ON: 7,
                                }
                            },
                        }
                    ]
                }
            },
        )
        await hass.async_block_till_done()
    assert len(hass.data[dynalite.DOMAIN]) == 1


async def test_async_setup_bad_config1(hass):
    """Test a successful with bad config on templates."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.available", True
    ):
        assert not await async_setup_component(
            hass,
            dynalite.DOMAIN,
            {
                dynalite.DOMAIN: {
                    dynalite.CONF_BRIDGES: [
                        {
                            dynalite.CONF_HOST: host,
                            dynalite.CONF_AREA: {
                                "1": {
                                    dynalite.CONF_NAME: "Name",
                                    dynalite.CONF_ROOM_ON: 7,
                                }
                            },
                        }
                    ]
                }
            },
        )
        await hass.async_block_till_done()
    assert dynalite.DOMAIN not in hass.data


async def test_async_setup_bad_config2(hass):
    """Test a successful with bad config on numbers."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.available", True
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
    assert dynalite.DOMAIN not in hass.data


async def test_async_setup_failed(hass):
    """Test a setup when DynaliteBridge.async_setup fails."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=False,
    ):
        assert await async_setup_component(
            hass,
            dynalite.DOMAIN,
            {dynalite.DOMAIN: {dynalite.CONF_BRIDGES: [{dynalite.CONF_HOST: host}]}},
        )
        await hass.async_block_till_done()
    assert hass.data[dynalite.DOMAIN] == {}


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    host = "1.2.3.4"
    entry = MockConfigEntry(domain=dynalite.DOMAIN, data={"host": host})
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.available", True
    ):
        assert await async_setup_component(
            hass,
            dynalite.DOMAIN,
            {dynalite.DOMAIN: {dynalite.CONF_BRIDGES: [{dynalite.CONF_HOST: host}]}},
        )
        await hass.async_block_till_done()
    assert hass.data[dynalite.DOMAIN].get(entry.entry_id)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data[dynalite.DOMAIN].get(entry.entry_id)
