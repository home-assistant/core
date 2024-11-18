"""The tests for the MQTT discovery."""

import copy
import json
from unittest.mock import ANY, patch

import pytest

from homeassistant.components.tasmota.const import DEFAULT_PREFIX
from homeassistant.components.tasmota.discovery import ALREADY_DISCOVERED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .conftest import setup_tasmota_helper
from .test_common import DEFAULT_CONFIG, DEFAULT_CONFIG_9_0_0_3, remove_device

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient, WebSocketGenerator


async def test_subscribing_config_topic(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test setting up discovery."""
    discovery_topic = DEFAULT_PREFIX

    assert mqtt_mock.async_subscribe.called
    mqtt_mock.async_subscribe.assert_any_call(
        discovery_topic + "/#", ANY, 0, "utf-8", ANY
    )


async def test_future_discovery_message(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we handle backwards compatible discovery messages."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["future_option"] = "BEST_SINCE_SLICED_BREAD"
    config["so"]["another_future_option"] = "EVEN_BETTER"

    with patch(
        "homeassistant.components.tasmota.discovery.tasmota_get_device_config",
        return_value={},
    ) as mock_tasmota_get_device_config:
        await setup_tasmota_helper(hass)

        async_fire_mqtt_message(
            hass, f"{DEFAULT_PREFIX}/00000049A3BC/config", json.dumps(config)
        )
        await hass.async_block_till_done()
        assert mock_tasmota_get_device_config.called


async def test_valid_discovery_message(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Test discovery callback called."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    with patch(
        "homeassistant.components.tasmota.discovery.tasmota_get_device_config",
        return_value={},
    ) as mock_tasmota_get_device_config:
        await setup_tasmota_helper(hass)

        async_fire_mqtt_message(
            hass, f"{DEFAULT_PREFIX}/00000049A3BC/config", json.dumps(config)
        )
        await hass.async_block_till_done()
        assert mock_tasmota_get_device_config.called


async def test_invalid_topic(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test receiving discovery message on wrong topic."""
    with patch(
        "homeassistant.components.tasmota.discovery.tasmota_get_device_config"
    ) as mock_tasmota_get_device_config:
        await setup_tasmota_helper(hass)

        async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/123456/configuration", "{}")
        await hass.async_block_till_done()
        assert not mock_tasmota_get_device_config.called


async def test_invalid_message(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Test receiving an invalid message."""
    with patch(
        "homeassistant.components.tasmota.discovery.tasmota_get_device_config"
    ) as mock_tasmota_get_device_config:
        await setup_tasmota_helper(hass)

        async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/123456/config", "asd")
        await hass.async_block_till_done()
        assert "Invalid discovery message" in caplog.text
        assert not mock_tasmota_get_device_config.called


async def test_invalid_mac(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Test topic is not matching device MAC."""
    config = copy.deepcopy(DEFAULT_CONFIG)

    with patch(
        "homeassistant.components.tasmota.discovery.tasmota_get_device_config"
    ) as mock_tasmota_get_device_config:
        await setup_tasmota_helper(hass)

        async_fire_mqtt_message(
            hass, f"{DEFAULT_PREFIX}/00000049A3BA/config", json.dumps(config)
        )
        await hass.async_block_till_done()
        assert "MAC mismatch" in caplog.text
        assert not mock_tasmota_get_device_config.called


async def test_correct_config_discovery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    setup_tasmota,
) -> None:
    """Test receiving valid discovery message."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None
    entity_entry = entity_registry.async_get("switch.tasmota_test")
    assert entity_entry is not None

    state = hass.states.get("switch.tasmota_test")
    assert state is not None
    assert state.name == "Tasmota Test"

    assert (mac, "switch", "relay", 0) in hass.data[ALREADY_DISCOVERED]


async def test_device_discover(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    setup_tasmota,
) -> None:
    """Test setting up a device."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None
    assert device_entry.configuration_url == f"http://{config['ip']}/"
    assert device_entry.manufacturer == "Tasmota"
    assert device_entry.model == config["md"]
    assert device_entry.name == config["dn"]
    assert device_entry.sw_version == config["sw"]


async def test_device_discover_deprecated(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    setup_tasmota,
) -> None:
    """Test setting up a device with deprecated discovery message."""
    config = copy.deepcopy(DEFAULT_CONFIG_9_0_0_3)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device and registry entries are created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None
    assert device_entry.manufacturer == "Tasmota"
    assert device_entry.model == config["md"]
    assert device_entry.name == config["dn"]
    assert device_entry.sw_version == config["sw"]


async def test_device_update(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    setup_tasmota,
) -> None:
    """Test updating a device."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["md"] = "Model 1"
    config["dn"] = "Name 1"
    config["sw"] = "v1.2.3.4"
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None

    # Update device parameters
    config["md"] = "Another model"
    config["dn"] = "Another name"
    config["sw"] = "v6.6.6"

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is updated
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None
    assert device_entry.model == "Another model"
    assert device_entry.name == "Another name"
    assert device_entry.sw_version == "v6.6.6"


async def test_device_remove(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    setup_tasmota,
) -> None:
    """Test removing a discovered device."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        "",
    )
    await hass.async_block_till_done()

    # Verify device entry is removed
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is None


async def test_device_remove_multiple_config_entries_1(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    setup_tasmota,
) -> None:
    """Test removing a discovered device."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    mock_entry = MockConfigEntry(domain="test")
    mock_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
    )

    tasmota_entry = hass.config_entries.async_entries("tasmota")[0]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None
    assert device_entry.config_entries == {tasmota_entry.entry_id, mock_entry.entry_id}

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        "",
    )
    await hass.async_block_till_done()

    # Verify device entry is not removed
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None
    assert device_entry.config_entries == {mock_entry.entry_id}


async def test_device_remove_multiple_config_entries_2(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    setup_tasmota,
) -> None:
    """Test removing a discovered device."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    mock_entry = MockConfigEntry(domain="test")
    mock_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
    )

    other_device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "other_device")},
    )

    tasmota_entry = hass.config_entries.async_entries("tasmota")[0]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None
    assert device_entry.config_entries == {tasmota_entry.entry_id, mock_entry.entry_id}
    assert other_device_entry.id != device_entry.id

    # Remove other config entry from the device
    device_registry.async_update_device(
        device_entry.id, remove_config_entry_id=mock_entry.entry_id
    )
    await hass.async_block_till_done()

    # Verify device entry is not removed
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None
    assert device_entry.config_entries == {tasmota_entry.entry_id}
    mqtt_mock.async_publish.assert_not_called()

    # Remove other config entry from the other device - Tasmota should not do any cleanup
    device_registry.async_update_device(
        other_device_entry.id, remove_config_entry_id=mock_entry.entry_id
    )
    await hass.async_block_till_done()
    mqtt_mock.async_publish.assert_not_called()


async def test_device_remove_stale(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    setup_tasmota,
) -> None:
    """Test removing a stale (undiscovered) device does not throw."""
    assert await async_setup_component(hass, "config", {})
    mac = "00000049A3BC"

    config_entry = hass.config_entries.async_entries("tasmota")[0]

    # Create a device
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
    )

    # Verify device entry was created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None

    # Remove the device
    await remove_device(hass, hass_ws_client, device_entry.id)

    # Verify device entry is removed
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is None


async def test_device_rediscover(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    setup_tasmota,
) -> None:
    """Test removing a device."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is created
    device_entry1 = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry1 is not None

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        "",
    )
    await hass.async_block_till_done()

    # Verify device entry is removed
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is None

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device entry is created, and id is reused
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, mac)}
    )
    assert device_entry is not None
    assert device_entry1.id == device_entry.id


async def test_entity_duplicate_discovery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
    setup_tasmota,
) -> None:
    """Test entities are not duplicated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.tasmota_test")
    state_duplicate = hass.states.get("binary_sensor.beer1")

    assert state is not None
    assert state.name == "Tasmota Test"
    assert state_duplicate is None
    assert (
        f"Entity already added, sending update: switch ('{mac}', 'switch', 'relay', 0)"
        in caplog.text
    )


async def test_entity_duplicate_removal(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
    setup_tasmota,
) -> None:
    """Test removing entity twice."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    config["rl"][0] = 0
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()
    assert f"Removing entity: switch ('{mac}', 'switch', 'relay', 0)" in caplog.text

    caplog.clear()
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{mac}/config", json.dumps(config))
    await hass.async_block_till_done()
    assert "Removing entity: switch" not in caplog.text


async def test_same_topic(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    setup_tasmota,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test detecting devices with same topic."""
    configs = [
        copy.deepcopy(DEFAULT_CONFIG),
        copy.deepcopy(DEFAULT_CONFIG),
        copy.deepcopy(DEFAULT_CONFIG),
    ]
    configs[0]["rl"][0] = 1
    configs[1]["rl"][0] = 1
    configs[2]["rl"][0] = 1
    configs[0]["mac"] = "000000000001"
    configs[1]["mac"] = "000000000002"
    configs[2]["mac"] = "000000000003"

    for config in configs[0:2]:
        async_fire_mqtt_message(
            hass,
            f"{DEFAULT_PREFIX}/{config['mac']}/config",
            json.dumps(config),
        )
    await hass.async_block_till_done()

    # Verify device registry entries are created for both devices
    for config in configs[0:2]:
        device_entry = device_registry.async_get_device(
            connections={(dr.CONNECTION_NETWORK_MAC, config["mac"])}
        )
        assert device_entry is not None
        assert device_entry.configuration_url == f"http://{config['ip']}/"
        assert device_entry.manufacturer == "Tasmota"
        assert device_entry.model == config["md"]
        assert device_entry.name == config["dn"]
        assert device_entry.sw_version == config["sw"]

    # Verify entities are created only for the first device
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, configs[0]["mac"])}
    )
    assert len(er.async_entries_for_device(entity_registry, device_entry.id, True)) == 1
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, configs[1]["mac"])}
    )
    assert len(er.async_entries_for_device(entity_registry, device_entry.id, True)) == 0

    # Verify a repairs issue was created
    issue_id = "topic_duplicated_tasmota_49A3BC/cmnd/"
    issue = issue_registry.async_get_issue("tasmota", issue_id)
    assert issue.data["mac"] == " ".join(config["mac"] for config in configs[0:2])

    # Discover a 3rd device with same topic
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{configs[2]['mac']}/config",
        json.dumps(configs[2]),
    )
    await hass.async_block_till_done()

    # Verify device registry entries was created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, configs[2]["mac"])}
    )
    assert device_entry is not None
    assert device_entry.configuration_url == f"http://{configs[2]['ip']}/"
    assert device_entry.manufacturer == "Tasmota"
    assert device_entry.model == configs[2]["md"]
    assert device_entry.name == configs[2]["dn"]
    assert device_entry.sw_version == configs[2]["sw"]

    # Verify no entities were created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, configs[2]["mac"])}
    )
    assert len(er.async_entries_for_device(entity_registry, device_entry.id, True)) == 0

    # Verify the repairs issue has been updated
    issue = issue_registry.async_get_issue("tasmota", issue_id)
    assert issue.data["mac"] == " ".join(config["mac"] for config in configs[0:3])

    # Rediscover 3rd device with fixed config
    configs[2]["t"] = "unique_topic_2"
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{configs[2]['mac']}/config",
        json.dumps(configs[2]),
    )
    await hass.async_block_till_done()

    # Verify entities are created also for the third device
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, configs[2]["mac"])}
    )
    assert len(er.async_entries_for_device(entity_registry, device_entry.id, True)) == 1

    # Verify the repairs issue has been updated
    issue = issue_registry.async_get_issue("tasmota", issue_id)
    assert issue.data["mac"] == " ".join(config["mac"] for config in configs[0:2])

    # Rediscover 2nd device with fixed config
    configs[1]["t"] = "unique_topic_1"
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{configs[1]['mac']}/config",
        json.dumps(configs[1]),
    )
    await hass.async_block_till_done()

    # Verify entities are created also for the second device
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, configs[1]["mac"])}
    )
    assert len(er.async_entries_for_device(entity_registry, device_entry.id, True)) == 1

    # Verify the repairs issue has been removed
    assert issue_registry.async_get_issue("tasmota", issue_id) is None


async def test_topic_no_prefix(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    setup_tasmota,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test detecting devices with same topic."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    config["ft"] = "%topic%/blah/"

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{config['mac']}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, config["mac"])}
    )
    assert device_entry is not None
    assert device_entry.configuration_url == f"http://{config['ip']}/"
    assert device_entry.manufacturer == "Tasmota"
    assert device_entry.model == config["md"]
    assert device_entry.name == config["dn"]
    assert device_entry.sw_version == config["sw"]

    # Verify entities are not created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, config["mac"])}
    )
    assert len(er.async_entries_for_device(entity_registry, device_entry.id, True)) == 0

    # Verify a repairs issue was created
    issue_id = "topic_no_prefix_00000049A3BC"
    assert ("tasmota", issue_id) in issue_registry.issues

    # Rediscover device with fixed config
    config["ft"] = "%topic%/%prefix%/"
    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{config['mac']}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    # Verify entities are created
    device_entry = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, config["mac"])}
    )
    assert len(er.async_entries_for_device(entity_registry, device_entry.id, True)) == 1

    # Verify the repairs issue has been removed
    assert ("tasmota", issue_id) not in issue_registry.issues
