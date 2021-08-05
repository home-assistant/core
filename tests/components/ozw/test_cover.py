"""Test Z-Wave Covers."""
from homeassistant.components.cover import ATTR_CURRENT_POSITION
from homeassistant.components.ozw.cover import VALUE_SELECTED_ID

from .common import setup_ozw

VALUE_ID = "Value"


async def test_cover(hass, cover_data, sent_messages, cover_msg):
    """Test setting up config entry."""
    receive_message = await setup_ozw(hass, fixture=cover_data)
    # Test loaded
    state = hass.states.get("cover.roller_shutter_3_instance_1_level")
    assert state is not None
    assert state.state == "closed"
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    # Test setting position
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.roller_shutter_3_instance_1_level", "position": 50},
        blocking=True,
    )
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 50, "ValueIDKey": 625573905}

    # Feedback on state
    cover_msg.decode()
    cover_msg.payload["Value"] = 50
    cover_msg.encode()
    receive_message(cover_msg)
    await hass.async_block_till_done()

    # Test opening
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.roller_shutter_3_instance_1_level"},
        blocking=True,
    )
    assert len(sent_messages) == 2
    msg = sent_messages[1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": True, "ValueIDKey": 281475602284568}

    # Test stopping after opening
    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.roller_shutter_3_instance_1_level"},
        blocking=True,
    )
    assert len(sent_messages) == 4
    msg = sent_messages[2]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": False, "ValueIDKey": 281475602284568}

    msg = sent_messages[3]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": False, "ValueIDKey": 562950578995224}

    # Test closing
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.roller_shutter_3_instance_1_level"},
        blocking=True,
    )
    assert len(sent_messages) == 5
    msg = sent_messages[4]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": True, "ValueIDKey": 562950578995224}

    # Test stopping after closing
    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.roller_shutter_3_instance_1_level"},
        blocking=True,
    )
    assert len(sent_messages) == 7
    msg = sent_messages[5]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": False, "ValueIDKey": 281475602284568}

    msg = sent_messages[6]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": False, "ValueIDKey": 562950578995224}

    # Test stopping after no open/close
    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.roller_shutter_3_instance_1_level"},
        blocking=True,
    )
    # both stop open/close messages sent
    assert len(sent_messages) == 9
    msg = sent_messages[7]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": False, "ValueIDKey": 281475602284568}

    msg = sent_messages[8]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": False, "ValueIDKey": 562950578995224}

    # Test converting position to zwave range for position > 0
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.roller_shutter_3_instance_1_level", "position": 100},
        blocking=True,
    )
    assert len(sent_messages) == 10
    msg = sent_messages[9]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 99, "ValueIDKey": 625573905}

    # Test converting position to zwave range for position = 0
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.roller_shutter_3_instance_1_level", "position": 0},
        blocking=True,
    )
    assert len(sent_messages) == 11
    msg = sent_messages[10]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 0, "ValueIDKey": 625573905}


async def test_barrier(hass, cover_gdo_data, sent_messages, cover_gdo_msg):
    """Test setting up config entry."""
    receive_message = await setup_ozw(hass, fixture=cover_gdo_data)
    # Test loaded
    state = hass.states.get("cover.gd00z_4_barrier_state")
    assert state is not None
    assert state.state == "closed"

    # Test opening
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.gd00z_4_barrier_state"},
        blocking=True,
    )
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 4, "ValueIDKey": 281475083239444}

    # Feedback on state
    cover_gdo_msg.decode()
    cover_gdo_msg.payload[VALUE_ID][VALUE_SELECTED_ID] = 4
    cover_gdo_msg.encode()
    receive_message(cover_gdo_msg)
    await hass.async_block_till_done()

    state = hass.states.get("cover.gd00z_4_barrier_state")
    assert state is not None
    assert state.state == "open"

    # Test closing
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.gd00z_4_barrier_state"},
        blocking=True,
    )
    assert len(sent_messages) == 2
    msg = sent_messages[1]
    assert msg["topic"] == "OpenZWave/1/command/setvalue/"
    assert msg["payload"] == {"Value": 0, "ValueIDKey": 281475083239444}
