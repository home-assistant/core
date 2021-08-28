"""Tests for the Sonos Media Player platform."""
from unittest.mock import PropertyMock

import pytest
from soco.exceptions import NotSupportedException

from homeassistant.components.sonos import DATA_SONOS, DOMAIN, media_player
from homeassistant.const import STATE_IDLE
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component


async def setup_platform(hass, config_entry, config):
    """Set up the media player platform for testing."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_async_setup_entry_hosts(hass, config_entry, config, soco):
    """Test static setup."""
    await setup_platform(hass, config_entry, config)

    speakers = list(hass.data[DATA_SONOS].discovered.values())
    speaker = speakers[0]
    assert speaker.soco == soco

    media_player = hass.states.get("media_player.zone_a")
    assert media_player.state == STATE_IDLE


async def test_async_setup_entry_discover(hass, config_entry, discover):
    """Test discovery setup."""
    await setup_platform(hass, config_entry, {})

    speakers = list(hass.data[DATA_SONOS].discovered.values())
    speaker = speakers[0]
    assert speaker.soco.uid == "RINCON_test"

    media_player = hass.states.get("media_player.zone_a")
    assert media_player.state == STATE_IDLE


async def test_discovery_ignore_unsupported_device(hass, config_entry, soco, caplog):
    """Test discovery setup."""
    message = f"GetVolume not supported on {soco.ip_address}"
    type(soco).volume = PropertyMock(side_effect=NotSupportedException(message))
    await setup_platform(hass, config_entry, {})

    assert message in caplog.text
    assert not hass.data[DATA_SONOS].discovered


async def test_services(hass, config_entry, config, hass_read_only_user):
    """Test join/unjoin requires control access."""
    await setup_platform(hass, config_entry, config)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            media_player.SERVICE_JOIN,
            {"master": "media_player.bla", "entity_id": "media_player.blub"},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )


async def test_device_registry(hass, config_entry, config, soco):
    """Test sonos device registered in the device registry."""
    await setup_platform(hass, config_entry, config)

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={("sonos", "RINCON_test")}
    )
    assert reg_device.model == "Model Name"
    assert reg_device.sw_version == "13.1"
    assert reg_device.connections == {(dr.CONNECTION_NETWORK_MAC, "00:11:22:33:44:55")}
    assert reg_device.manufacturer == "Sonos"
    assert reg_device.suggested_area == "Zone A"
    assert reg_device.name == "Zone A"


async def test_entity_basic(hass, config_entry, discover):
    """Test basic state and attributes."""
    await setup_platform(hass, config_entry, {})

    state = hass.states.get("media_player.zone_a")
    assert state.state == STATE_IDLE
    attributes = state.attributes
    assert attributes["friendly_name"] == "Zone A"
    assert attributes["is_volume_muted"] is False
    assert attributes["night_sound"] is True
    assert attributes["speech_enhance"] is True
    assert attributes["volume_level"] == 0.19
