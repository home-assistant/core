"""Test Dynalite __init__."""


import homeassistant.components.dynalite.const as dynalite
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_ROOM
from homeassistant.setup import async_setup_component

from tests.async_mock import call, patch
from tests.common import MockConfigEntry


async def test_empty_config(hass):
    """Test with an empty config."""
    assert await async_setup_component(hass, dynalite.DOMAIN, {}) is True
    assert len(hass.config_entries.flow.async_progress()) == 0
    assert len(hass.config_entries.async_entries(dynalite.DOMAIN)) == 0


async def test_async_setup(hass):
    """Test a successful setup with all of the different options."""
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
                            CONF_HOST: "1.2.3.4",
                            CONF_PORT: 1234,
                            dynalite.CONF_AUTO_DISCOVER: True,
                            dynalite.CONF_POLL_TIMER: 5.5,
                            dynalite.CONF_AREA: {
                                "1": {
                                    CONF_NAME: "Name1",
                                    dynalite.CONF_CHANNEL: {"4": {}},
                                    dynalite.CONF_PRESET: {"7": {}},
                                    dynalite.CONF_NO_DEFAULT: True,
                                },
                                "2": {CONF_NAME: "Name2"},
                                "3": {
                                    CONF_NAME: "Name3",
                                    dynalite.CONF_TEMPLATE: CONF_ROOM,
                                },
                                "4": {
                                    CONF_NAME: "Name4",
                                    dynalite.CONF_TEMPLATE: dynalite.CONF_TIME_COVER,
                                },
                            },
                            dynalite.CONF_DEFAULT: {dynalite.CONF_FADE: 2.3},
                            dynalite.CONF_ACTIVE: dynalite.ACTIVE_INIT,
                            dynalite.CONF_PRESET: {
                                "5": {CONF_NAME: "pres5", dynalite.CONF_FADE: 4.5}
                            },
                            dynalite.CONF_TEMPLATE: {
                                CONF_ROOM: {
                                    dynalite.CONF_ROOM_ON: 6,
                                    dynalite.CONF_ROOM_OFF: 7,
                                },
                                dynalite.CONF_TIME_COVER: {
                                    dynalite.CONF_OPEN_PRESET: 8,
                                    dynalite.CONF_CLOSE_PRESET: 9,
                                    dynalite.CONF_STOP_PRESET: 10,
                                    dynalite.CONF_CHANNEL_COVER: 3,
                                    dynalite.CONF_DURATION: 2.2,
                                    dynalite.CONF_TILT_TIME: 3.3,
                                    dynalite.CONF_DEVICE_CLASS: "awning",
                                },
                            },
                        }
                    ]
                }
            },
        )
        await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(dynalite.DOMAIN)) == 1


async def test_async_setup_bad_config1(hass):
    """Test a successful with bad config on templates."""
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
                            CONF_HOST: "1.2.3.4",
                            dynalite.CONF_AREA: {
                                "1": {
                                    dynalite.CONF_TEMPLATE: dynalite.CONF_TIME_COVER,
                                    CONF_NAME: "Name",
                                    dynalite.CONF_ROOM_ON: 7,
                                }
                            },
                        }
                    ]
                }
            },
        )
        await hass.async_block_till_done()


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
                            CONF_HOST: host,
                            dynalite.CONF_AREA: {"WRONG": {CONF_NAME: "Name"}},
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
    entry = MockConfigEntry(domain=dynalite.DOMAIN, data={CONF_HOST: host})
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
