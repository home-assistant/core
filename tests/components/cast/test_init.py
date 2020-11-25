"""Tests for the Cast config flow."""
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import cast, websocket_api
from homeassistant.setup import async_setup_component

from .conftest import async_setup_media_player_cast, get_fake_chromecast_info

from tests.async_mock import patch
from tests.common import MockConfigEntry, mock_device_registry, mock_registry


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_creating_entry_sets_up_media_player(hass):
    """Test setting up Cast loads the media player."""
    with patch(
        "homeassistant.components.cast.media_player.async_setup_entry",
        return_value=True,
    ) as mock_setup, patch(
        "pychromecast.discovery.discover_chromecasts", return_value=(True, None)
    ), patch(
        "pychromecast.discovery.stop_discovery"
    ):
        result = await hass.config_entries.flow.async_init(
            cast.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_cast_creates_entry(hass):
    """Test that specifying config will create an entry."""
    with patch(
        "homeassistant.components.cast.async_setup_entry", return_value=True
    ) as mock_setup:
        await async_setup_component(
            hass, cast.DOMAIN, {"cast": {"some_config": "to_trigger_import"}}
        )
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_not_configuring_cast_not_creates_entry(hass):
    """Test that no config will not create an entry."""
    with patch(
        "homeassistant.components.cast.async_setup_entry", return_value=True
    ) as mock_setup:
        await async_setup_component(hass, cast.DOMAIN, {})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0


async def test_device_remove(hass, device_reg, entity_reg):
    """Test removing a discovered device through device registry."""
    entity_id = "media_player.speaker"
    info = get_fake_chromecast_info()
    mangled_uuid = info.uuid.replace("-", "")

    await async_setup_media_player_cast(hass, info)
    await hass.async_block_till_done()

    # Verify device and entity are created
    device_entry = device_reg.async_get_device({("cast", mangled_uuid)}, set())
    assert device_entry is not None
    entity_entry = entity_reg.async_get_entity_id("media_player", "cast", info.uuid)
    assert entity_entry is not None
    state = hass.states.get(entity_id)
    assert state is not None

    device_reg.async_remove_device(device_entry.id)
    await hass.async_block_till_done()

    # Verify device and entity are removed
    device_entry = device_reg.async_get_device({("cast", mangled_uuid)}, set())
    assert device_entry is None
    entity_entry = entity_reg.async_get_entity_id("media_player", "cast", info.uuid)
    assert entity_entry is None
    state = hass.states.get(entity_id)
    assert state is None


async def test_cast_ws_remove_discovered_device(
    hass, device_reg, entity_reg, hass_ws_client
):
    """Test Cast websocket device removal."""
    info = get_fake_chromecast_info()
    mangled_uuid = info.uuid.replace("-", "")
    await async_setup_media_player_cast(hass, info)

    # Verify device entry is created
    device_entry = device_reg.async_get_device({("cast", mangled_uuid)}, set())
    assert device_entry is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "cast/device/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    assert response["success"]

    # Verify device entry is cleared
    device_entry = device_reg.async_get_device({("cast", mangled_uuid)}, set())
    assert device_entry is None


async def test_cast_ws_remove_discovered_device_twice(hass, device_reg, hass_ws_client):
    """Test Cast websocket device removal."""
    info = get_fake_chromecast_info()
    mangled_uuid = info.uuid.replace("-", "")
    await async_setup_media_player_cast(hass, info)

    # Verify device entry is created
    device_entry = device_reg.async_get_device({("cast", mangled_uuid)}, set())
    assert device_entry is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "cast/device/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    assert response["success"]

    await client.send_json(
        {"id": 6, "type": "cast/device/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == websocket_api.const.ERR_NOT_FOUND
    assert response["error"]["message"] == "Device not found"


async def test_cast_ws_remove_non_tasmota_device(hass, device_reg, hass_ws_client):
    """Test Cast websocket device removal of device belonging to other domain."""
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    info = get_fake_chromecast_info()
    await async_setup_media_player_cast(hass, info)

    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={("mac", "12:34:56:AB:CD:EF")},
    )
    assert device_entry is not None

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "cast/device/remove", "device_id": device_entry.id}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == websocket_api.const.ERR_NOT_FOUND
