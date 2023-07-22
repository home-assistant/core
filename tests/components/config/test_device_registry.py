"""Test device_registry API."""
import pytest

from homeassistant.components.config import device_registry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
def client(hass, hass_ws_client):
    """Fixture that can interact with the config manager API."""
    hass.loop.run_until_complete(device_registry.async_setup(hass))
    return hass.loop.run_until_complete(hass_ws_client(hass))


async def test_list_devices(
    hass: HomeAssistant, client, device_registry: dr.DeviceRegistry
) -> None:
    """Test list entries."""
    device1 = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    device2 = device_registry.async_get_or_create(
        config_entry_id="1234",
        identifiers={("bridgeid", "1234")},
        manufacturer="manufacturer",
        model="model",
        via_device=("bridgeid", "0123"),
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    await client.send_json({"id": 5, "type": "config/device_registry/list"})
    msg = await client.receive_json()

    dev1, dev2 = (entry.pop("id") for entry in msg["result"])

    assert msg["result"] == [
        {
            "area_id": None,
            "config_entries": ["1234"],
            "configuration_url": None,
            "connections": [["ethernet", "12:34:56:78:90:AB:CD:EF"]],
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "identifiers": [["bridgeid", "0123"]],
            "manufacturer": "manufacturer",
            "model": "model",
            "name_by_user": None,
            "name": None,
            "sw_version": None,
            "via_device_id": None,
        },
        {
            "area_id": None,
            "config_entries": ["1234"],
            "configuration_url": None,
            "connections": [],
            "disabled_by": None,
            "entry_type": dr.DeviceEntryType.SERVICE,
            "hw_version": None,
            "identifiers": [["bridgeid", "1234"]],
            "manufacturer": "manufacturer",
            "model": "model",
            "name_by_user": None,
            "name": None,
            "sw_version": None,
            "via_device_id": dev1,
        },
    ]

    class Unserializable:
        """Good luck serializing me."""

    device_registry.async_update_device(device2.id, name=Unserializable())
    await hass.async_block_till_done()

    await client.send_json({"id": 6, "type": "config/device_registry/list"})
    msg = await client.receive_json()

    assert msg["result"] == [
        {
            "area_id": None,
            "config_entries": ["1234"],
            "configuration_url": None,
            "connections": [["ethernet", "12:34:56:78:90:AB:CD:EF"]],
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "id": device1.id,
            "identifiers": [["bridgeid", "0123"]],
            "manufacturer": "manufacturer",
            "model": "model",
            "name_by_user": None,
            "name": None,
            "sw_version": None,
            "via_device_id": None,
        }
    ]

    # Remove the bad device to avoid errors when test is being torn down
    device_registry.async_remove_device(device2.id)


@pytest.mark.parametrize(
    ("payload_key", "payload_value"),
    [
        ["area_id", "12345A"],
        ["area_id", None],
        ["disabled_by", dr.DeviceEntryDisabler.USER],
        ["disabled_by", "user"],
        ["disabled_by", None],
        ["name_by_user", "Test Friendly Name"],
        ["name_by_user", None],
    ],
)
async def test_update_device(
    hass: HomeAssistant,
    client,
    device_registry: dr.DeviceRegistry,
    payload_key,
    payload_value,
) -> None:
    """Test update entry."""
    device = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert not getattr(device, payload_key)

    await client.send_json(
        {
            "id": 1,
            "type": "config/device_registry/update",
            "device_id": device.id,
            payload_key: payload_value,
        }
    )

    msg = await client.receive_json()
    await hass.async_block_till_done()
    assert len(device_registry.devices) == 1

    device = device_registry.async_get_device(
        identifiers={("bridgeid", "0123")},
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
    )

    assert msg["result"][payload_key] == payload_value
    assert getattr(device, payload_key) == payload_value

    assert isinstance(device.disabled_by, (dr.DeviceEntryDisabler, type(None)))


async def test_remove_config_entry_from_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing config entry from device."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    can_remove = False

    async def async_remove_config_entry_device(hass, config_entry, device_entry):
        return can_remove

    mock_integration(
        hass,
        MockModule(
            "comp1", async_remove_config_entry_device=async_remove_config_entry_device
        ),
    )
    mock_integration(
        hass,
        MockModule(
            "comp2", async_remove_config_entry_device=async_remove_config_entry_device
        ),
    )

    entry_1 = MockConfigEntry(
        domain="comp1",
        title="Test 1",
        source="bla",
    )
    entry_1.supports_remove_device = True
    entry_1.add_to_hass(hass)

    entry_2 = MockConfigEntry(
        domain="comp1",
        title="Test 1",
        source="bla",
    )
    entry_2.supports_remove_device = True
    entry_2.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert device_entry.config_entries == {entry_1.entry_id, entry_2.entry_id}

    # Try removing a config entry from the device, it should fail because
    # async_remove_config_entry_device returns False
    await ws_client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": entry_1.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unknown_error"

    # Make async_remove_config_entry_device return True
    can_remove = True

    # Remove the 1st config entry
    await ws_client.send_json(
        {
            "id": 6,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": entry_1.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"]["config_entries"] == [entry_2.entry_id]

    # Check that the config entry was removed from the device
    assert device_registry.async_get(device_entry.id).config_entries == {
        entry_2.entry_id
    }

    # Remove the 2nd config entry
    await ws_client.send_json(
        {
            "id": 7,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": entry_2.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"] is None

    # This was the last config entry, the device is removed
    assert not device_registry.async_get(device_entry.id)


async def test_remove_config_entry_from_device_fails(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing config entry from device failing cases."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    async def async_remove_config_entry_device(hass, config_entry, device_entry):
        return True

    mock_integration(
        hass,
        MockModule("comp1"),
    )
    mock_integration(
        hass,
        MockModule(
            "comp2", async_remove_config_entry_device=async_remove_config_entry_device
        ),
    )

    entry_1 = MockConfigEntry(
        domain="comp1",
        title="Test 1",
        source="bla",
    )
    entry_1.add_to_hass(hass)

    entry_2 = MockConfigEntry(
        domain="comp2",
        title="Test 1",
        source="bla",
    )
    entry_2.supports_remove_device = True
    entry_2.add_to_hass(hass)

    entry_3 = MockConfigEntry(
        domain="comp3",
        title="Test 1",
        source="bla",
    )
    entry_3.supports_remove_device = True
    entry_3.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry_3.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert device_entry.config_entries == {
        entry_1.entry_id,
        entry_2.entry_id,
        entry_3.entry_id,
    }

    fake_entry_id = "abc123"
    assert entry_1.entry_id != fake_entry_id
    fake_device_id = "abc123"
    assert device_entry.id != fake_device_id

    # Try removing a non existing config entry from the device
    await ws_client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": fake_entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unknown_error"
    assert response["error"]["message"] == "Unknown config entry"

    # Try removing a config entry which does not support removal from the device
    await ws_client.send_json(
        {
            "id": 6,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": entry_1.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unknown_error"
    assert (
        response["error"]["message"] == "Config entry does not support device removal"
    )

    # Try removing a config entry from a device which does not exist
    await ws_client.send_json(
        {
            "id": 7,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": entry_2.entry_id,
            "device_id": fake_device_id,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unknown_error"
    assert response["error"]["message"] == "Unknown device"

    # Try removing a config entry from a device which it's not connected to
    await ws_client.send_json(
        {
            "id": 8,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": entry_2.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()

    assert response["success"]
    assert set(response["result"]["config_entries"]) == {
        entry_1.entry_id,
        entry_3.entry_id,
    }

    await ws_client.send_json(
        {
            "id": 9,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": entry_2.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unknown_error"
    assert response["error"]["message"] == "Config entry not in device"

    # Try removing a config entry which can't be loaded from a device - allowed
    await ws_client.send_json(
        {
            "id": 10,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": entry_3.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "unknown_error"
    assert response["error"]["message"] == "Integration not found"
