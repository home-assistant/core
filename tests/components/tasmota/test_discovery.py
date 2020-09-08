"""The tests for the MQTT discovery."""
import copy
import json

from hatasmota.const import CONF_ONLINE
import pytest

from homeassistant.components.tasmota.const import DEFAULT_PREFIX
from homeassistant.components.tasmota.discovery import ALREADY_DISCOVERED

from .conftest import setup_tasmota

from tests.async_mock import AsyncMock, patch
from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG = {
    "dn": "My Device",
    "fn": ["Beer", "Milk", "Three", "Four", "Five"],
    "hn": "tasmota_49A3BC",
    "id": "49A3BC",
    "md": "Sonoff 123",
    "ofl": "offline",
    CONF_ONLINE: "online",
    "state": ["OFF", "ON", "TOGGLE", "HOLD"],
    "sw": "2.3.3.4",
    "t": "tasmota_49A3BC",
    "t_f": "%topic%/%prefix%/",
    "t_p": ["cmnd", "stat", "tele"],
    "li": [0, 0, 0, 0, 0, 0, 0, 0],
    "rl": [0, 0, 0, 0, 0, 0, 0, 0],
    "se": [],
    "ver": 1,
}


async def test_subscribing_config_topic(hass, mqtt_mock):
    """Test setting up discovery."""
    await setup_tasmota(hass)

    discovery_topic = DEFAULT_PREFIX

    assert mqtt_mock.async_subscribe.called
    call_args = mqtt_mock.async_subscribe.mock_calls[0][1]
    assert call_args[0] == discovery_topic + "/#"
    assert call_args[2] == 0


async def test_invalid_topic(hass, mqtt_mock):
    """Test receiving discovery message on wrong topic."""
    await setup_tasmota(hass)
    with patch(
        "homeassistant.components.tasmota.discovery.async_dispatcher_send"
    ) as mock_dispatcher_send:
        mock_dispatcher_send = AsyncMock(return_value=None)

        async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/123456/configuration", "{}")
        await hass.async_block_till_done()
        assert not mock_dispatcher_send.called


async def test_invalid_message(hass, mqtt_mock, caplog):
    """Test receiving an invalid message."""
    await setup_tasmota(hass)
    with patch(
        "homeassistant.components.tasmota.discovery.async_dispatcher_send"
    ) as mock_dispatcher_send:
        mock_dispatcher_send = AsyncMock(return_value=None)

        async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/123456/config", "asd")
        await hass.async_block_till_done()
        assert "Invalid discovery message" in caplog.text
        assert not mock_dispatcher_send.called


async def test_invalid_id(hass, mqtt_mock, caplog):
    """Test topic is not matching device ID."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    await setup_tasmota(hass)
    with patch(
        "homeassistant.components.tasmota.discovery.async_dispatcher_send"
    ) as mock_dispatcher_send:
        mock_dispatcher_send = AsyncMock(return_value=None)

        async_fire_mqtt_message(
            hass, f"{DEFAULT_PREFIX}/49A3BA/config", json.dumps(config)
        )
        await hass.async_block_till_done()
        assert "Serial number mismatch" in caplog.text
        assert not mock_dispatcher_send.called


async def test_correct_config_discovery(
    hass, mqtt_mock, caplog, device_reg, entity_reg
):
    """Test receiving valid discovery message."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1

    await setup_tasmota(hass)

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is not None
    entity_entry = entity_reg.async_get("switch.beer")
    assert entity_entry is not None

    state = hass.states.get("switch.beer")
    assert state is not None
    assert state.name == "Beer"

    assert ("49A3BC", "switch", 0) in hass.data[ALREADY_DISCOVERED]


async def test_device_discover(hass, mqtt_mock, caplog, device_reg, entity_reg):
    """Test setting up a device."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    await setup_tasmota(hass)

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is not None
    assert device_entry.manufacturer == "Tasmota"
    assert device_entry.model == config["md"]
    assert device_entry.name == config["dn"]
    assert device_entry.sw_version == config["sw"]


async def test_device_update(hass, mqtt_mock, caplog, device_reg, entity_reg):
    """Test updating a device."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["md"] = "Model 1"
    config["dn"] = "Name 1"
    config["sw"] = "v1.2.3.4"

    await setup_tasmota(hass)

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is not None

    # Update device parameters
    config["md"] = "Another model"
    config["dn"] = "Another name"
    config["sw"] = "v6.6.6"

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is updated
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is not None
    assert device_entry.model == "Another model"
    assert device_entry.name == "Another name"
    assert device_entry.sw_version == "v6.6.6"


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock, caplog, device_reg):
    """Test handling of exception when creating discovered device."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    data = json.dumps(config)

    await setup_tasmota(hass)

    # Trigger an exception when the entity is added
    with patch(
        "hatasmota.discovery.get_device_config_helper",
        return_value=object(),
    ):
        async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/49A3BC/config", data)
        await hass.async_block_till_done()

    # Verify device entry is not created
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is None
    assert (
        "Exception in async_discover_device when dispatching 'tasmota_discovery_device'"
        in caplog.text
    )

    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/49A3BC/config", data)
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is not None


async def test_device_remove(hass, mqtt_mock, caplog, device_reg, entity_reg):
    """Test removing a discovered device."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    await setup_tasmota(hass)

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is not None

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        "",
    )
    await hass.async_block_till_done()

    # Verify device entry is removed
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is None


async def test_device_remove_stale(hass, mqtt_mock, caplog, device_reg):
    """Test removing a stale (undiscovered) device does not throw."""
    await setup_tasmota(hass)
    config_entry = hass.config_entries.async_entries("tasmota")[0]

    # Create a device
    device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("tasmota", "49A3BC")},
    )

    # Verify device entry was created
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is not None

    # Remove the device
    device_reg.async_remove_device(device_entry.id)

    # Verify device entry is removed
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is None


async def test_device_rediscover(hass, mqtt_mock, caplog, device_reg, entity_reg):
    """Test removing a device."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    await setup_tasmota(hass)

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry1 = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry1 is not None

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        "",
    )
    await hass.async_block_till_done()

    # Verify device entry is removed
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is None

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is created, and id is reused
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is not None
    assert device_entry1.id == device_entry.id


async def test_entity_duplicate_discovery(hass, mqtt_mock, caplog):
    """Test entities are not duplicated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1

    await setup_tasmota(hass)

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        json.dumps(config),
    )
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.beer")
    state_duplicate = hass.states.get("binary_sensor.beer1")

    assert state is not None
    assert state.name == "Beer"
    assert state_duplicate is None
    assert (
        "Entity already added, sending update: switch ('49A3BC', 'switch', 0)"
        in caplog.text
    )


async def test_entity_duplicate_removal(hass, mqtt_mock, caplog):
    """Test removing entity twice."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1

    await setup_tasmota(hass)

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    config["rl"][0] = 0
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/49A3BC/config", json.dumps(config))
    await hass.async_block_till_done()
    assert "Removing entity: switch ('49A3BC', 'switch', 0)" in caplog.text

    caplog.clear()
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/49A3BC/config", json.dumps(config))
    await hass.async_block_till_done()
    assert "Removing entity: switch ('49A3BC', 'switch', 0)" not in caplog.text


async def test_entity_cleanup(hass, device_reg, entity_reg, mqtt_mock):
    """Test discovered device and entity is cleaned up when removed from registry."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1

    await setup_tasmota(hass)

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/49A3BC/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    entity_id = "switch.beer"

    # Verify device and entity registry entries are created
    device_entry = device_reg.async_get_device({("tasmota", "49A3BC")}, set())
    assert device_entry is not None
    entity_entry = entity_reg.async_get(entity_id)
    assert entity_entry is not None

    state = hass.states.get(entity_id)
    assert state is not None

    device_reg.async_remove_device(device_entry.id)
    await hass.async_block_till_done()

    # Verify device and entity registry entries are cleared
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    assert device_entry is None
    entity_entry = entity_reg.async_get(entity_id)
    assert entity_entry is None

    # Verify state is removed
    state = hass.states.get(entity_id)
    assert state is None
    await hass.async_block_till_done()

    # Verify retained discovery topic has been cleared
    mqtt_mock.async_publish.assert_called_once_with(
        f"{DEFAULT_PREFIX}/49A3BC/config", "", 0, True
    )
