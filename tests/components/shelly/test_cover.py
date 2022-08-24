"""The scene tests for the myq platform."""
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers.entity_component import async_update_entity

ROLLER_BLOCK_ID = 1


async def test_block_device_services(hass, coap_wrapper, monkeypatch):
    """Test block device cover services."""
    assert coap_wrapper

    monkeypatch.setitem(coap_wrapper.device.settings, "mode", "roller")
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, COVER_DOMAIN)
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test_name", ATTR_POSITION: 50},
        blocking=True,
    )
    state = hass.states.get("cover.test_name")
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_name"},
        blocking=True,
    )
    assert hass.states.get("cover.test_name").state == STATE_OPENING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_name"},
        blocking=True,
    )
    assert hass.states.get("cover.test_name").state == STATE_CLOSING

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.test_name"},
        blocking=True,
    )
    assert hass.states.get("cover.test_name").state == STATE_CLOSED


async def test_block_device_update(hass, coap_wrapper, monkeypatch):
    """Test block device update."""
    assert coap_wrapper

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, COVER_DOMAIN)
    )
    await hass.async_block_till_done()

    monkeypatch.setattr(coap_wrapper.device.blocks[ROLLER_BLOCK_ID], "rollerPos", 0)
    await async_update_entity(hass, "cover.test_name")
    await hass.async_block_till_done()
    assert hass.states.get("cover.test_name").state == STATE_CLOSED

    monkeypatch.setattr(coap_wrapper.device.blocks[ROLLER_BLOCK_ID], "rollerPos", 100)
    await async_update_entity(hass, "cover.test_name")
    await hass.async_block_till_done()
    assert hass.states.get("cover.test_name").state == STATE_OPEN


async def test_block_device_no_roller_blocks(hass, coap_wrapper, monkeypatch):
    """Test block device without roller blocks."""
    assert coap_wrapper

    monkeypatch.setattr(coap_wrapper.device.blocks[ROLLER_BLOCK_ID], "type", None)
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, COVER_DOMAIN)
    )
    await hass.async_block_till_done()
    assert hass.states.get("cover.test_name") is None


async def test_rpc_device_services(hass, rpc_wrapper, monkeypatch):
    """Test RPC device cover services."""
    assert rpc_wrapper

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, COVER_DOMAIN)
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test_cover_0", ATTR_POSITION: 50},
        blocking=True,
    )
    state = hass.states.get("cover.test_cover_0")
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    monkeypatch.setitem(rpc_wrapper.device.status["cover:0"], "state", "opening")
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover_0"},
        blocking=True,
    )
    rpc_wrapper.async_set_updated_data("")
    assert hass.states.get("cover.test_cover_0").state == STATE_OPENING

    monkeypatch.setitem(rpc_wrapper.device.status["cover:0"], "state", "closing")
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover_0"},
        blocking=True,
    )
    rpc_wrapper.async_set_updated_data("")
    assert hass.states.get("cover.test_cover_0").state == STATE_CLOSING

    monkeypatch.setitem(rpc_wrapper.device.status["cover:0"], "state", "closed")
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.test_cover_0"},
        blocking=True,
    )
    rpc_wrapper.async_set_updated_data("")
    assert hass.states.get("cover.test_cover_0").state == STATE_CLOSED


async def test_rpc_device_no_cover_keys(hass, rpc_wrapper, monkeypatch):
    """Test RPC device without cover keys."""
    assert rpc_wrapper

    monkeypatch.delitem(rpc_wrapper.device.status, "cover:0")

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, COVER_DOMAIN)
    )
    await hass.async_block_till_done()
    assert hass.states.get("cover.test_cover_0") is None


async def test_rpc_device_update(hass, rpc_wrapper, monkeypatch):
    """Test RPC device update."""
    assert rpc_wrapper

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, COVER_DOMAIN)
    )
    await hass.async_block_till_done()

    monkeypatch.setitem(rpc_wrapper.device.status["cover:0"], "state", "closed")
    await async_update_entity(hass, "cover.test_cover_0")
    await hass.async_block_till_done()
    assert hass.states.get("cover.test_cover_0").state == STATE_CLOSED

    monkeypatch.setitem(rpc_wrapper.device.status["cover:0"], "state", "open")
    await async_update_entity(hass, "cover.test_cover_0")
    await hass.async_block_till_done()
    assert hass.states.get("cover.test_cover_0").state == STATE_OPEN


async def test_rpc_device_no_position_control(hass, rpc_wrapper, monkeypatch):
    """Test RPC device with no position control."""
    assert rpc_wrapper

    monkeypatch.setitem(rpc_wrapper.device.status["cover:0"], "pos_control", False)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, COVER_DOMAIN)
    )
    await hass.async_block_till_done()

    await async_update_entity(hass, "cover.test_cover_0")
    await hass.async_block_till_done()
    assert hass.states.get("cover.test_cover_0").state == STATE_OPEN
