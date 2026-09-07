"""Test device_registry API."""

from datetime import datetime
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_unordered import unordered

from homeassistant.components.config import DOMAIN, device_registry
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, label_registry as lr
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, MockModule, mock_integration
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture(name="client")
async def client_fixture(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """Fixture that can interact with the config manager API."""
    device_registry.async_setup(hass)
    return await hass_ws_client(hass)


@pytest.mark.usefixtures("freezer")
async def test_list_devices(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test list entries."""
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)
    device1 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    device2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("bridgeid", "1234")},
        manufacturer="manufacturer",
        model="model",
        via_device_id=device1.id,
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    await client.send_json_auto_id({"type": "config/device_registry/list"})
    msg = await client.receive_json()

    dev1, _ = (entry.pop("id") for entry in msg["result"])

    assert msg["result"] == [
        {
            "area_id": None,
            "config_entries": [entry.entry_id],
            "config_entries_subentries": {entry.entry_id: [None]},
            "config_entry_id": entry.entry_id,
            "config_subentry_id": None,
            "configuration_url": None,
            "connections": [["ethernet", "12:34:56:78:90:AB:CD:EF"]],
            "created_at": utcnow().timestamp(),
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "identifiers": [["bridgeid", "0123"]],
            "labels": [],
            "manufacturer": "manufacturer",
            "model": "model",
            "model_id": None,
            "modified_at": utcnow().timestamp(),
            "name_by_user": None,
            "name": None,
            "parent_device_id": None,
            "primary_config_entry": entry.entry_id,
            "serial_number": None,
            "sw_version": None,
            "via_device_id": None,
        },
        {
            "area_id": None,
            "config_entries": [entry.entry_id],
            "config_entries_subentries": {entry.entry_id: [None]},
            "config_entry_id": entry.entry_id,
            "config_subentry_id": None,
            "configuration_url": None,
            "connections": [],
            "created_at": utcnow().timestamp(),
            "disabled_by": None,
            "entry_type": dr.DeviceEntryType.SERVICE,
            "hw_version": None,
            "identifiers": [["bridgeid", "1234"]],
            "labels": [],
            "manufacturer": "manufacturer",
            "model": "model",
            "model_id": None,
            "modified_at": utcnow().timestamp(),
            "name_by_user": None,
            "name": None,
            "parent_device_id": None,
            "primary_config_entry": entry.entry_id,
            "serial_number": None,
            "sw_version": None,
            "via_device_id": dev1,
        },
    ]

    class Unserializable:
        """Good luck serializing me."""

    device_registry.async_update_device(device2.id, name=Unserializable())
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "config/device_registry/list"})
    msg = await client.receive_json()

    assert msg["result"] == [
        {
            "area_id": None,
            "config_entries": [entry.entry_id],
            "config_entries_subentries": {entry.entry_id: [None]},
            "config_entry_id": entry.entry_id,
            "config_subentry_id": None,
            "configuration_url": None,
            "connections": [["ethernet", "12:34:56:78:90:AB:CD:EF"]],
            "created_at": utcnow().timestamp(),
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "id": device1.id,
            "identifiers": [["bridgeid", "0123"]],
            "labels": [],
            "manufacturer": "manufacturer",
            "model": "model",
            "model_id": None,
            "modified_at": utcnow().timestamp(),
            "name_by_user": None,
            "name": None,
            "parent_device_id": None,
            "primary_config_entry": entry.entry_id,
            "serial_number": None,
            "sw_version": None,
            "via_device_id": None,
        }
    ]

    # Remove the bad device to avoid errors when test is being torn down
    device_registry.async_remove_device(device2.id)


def _storage_device_v1_12(
    device_id: str,
    config_entries: list[str],
    primary_config_entry: str | None,
    identifier: str,
) -> dict[str, Any]:
    """Return a stored device in version 1.12 format."""
    return {
        "area_id": None,
        "config_entries": config_entries,
        "config_entries_subentries": {
            config_entry: [None] for config_entry in config_entries
        },
        "configuration_url": None,
        "connections": [],
        "created_at": "1970-01-01T00:00:00+00:00",
        "disabled_by": None,
        "entry_type": None,
        "hw_version": None,
        "id": device_id,
        "identifiers": [["test", identifier]],
        "labels": [],
        "manufacturer": None,
        "model": None,
        "model_id": None,
        "modified_at": "1970-01-01T00:00:00+00:00",
        "name": None,
        "name_by_user": None,
        "primary_config_entry": primary_config_entry,
        "serial_number": None,
        "sw_version": None,
        "via_device_id": None,
    }


@pytest.mark.parametrize("load_registries", [False])
async def test_list_composite_splits(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    hass_storage: dict[str, Any],
) -> None:
    """Test listing the devices pre-migration composite devices were split into."""
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)
    entry_3 = MockConfigEntry()
    entry_3.add_to_hass(hass)

    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                # Composite spanning two config entries, with entry_1 as primary
                _storage_device_v1_12(
                    "compositea000000000000000000000",
                    [entry_1.entry_id, entry_2.entry_id],
                    entry_1.entry_id,
                    "a",
                ),
                # Composite spanning two config entries, without a primary
                _storage_device_v1_12(
                    "compositeb000000000000000000000",
                    [entry_1.entry_id, entry_3.entry_id],
                    None,
                    "b",
                ),
                # Single config entry device, not split
                _storage_device_v1_12(
                    "single0000000000000000000000000",
                    [entry_1.entry_id],
                    entry_1.entry_id,
                    "c",
                ),
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    # pylint: disable-next=home-assistant-tests-registry-fixtures
    registry = dr.async_get(hass)

    splits_a = registry.async_get_devices_for_composite_device_id(
        "compositea000000000000000000000"
    )
    splits_b = registry.async_get_devices_for_composite_device_id(
        "compositeb000000000000000000000"
    )
    assert len(splits_a) == 2
    assert len(splits_b) == 2
    primary_a = next(
        device for device in splits_a if device.config_entry_id == entry_1.entry_id
    )

    await client.send_json_auto_id(
        {"type": "config/device_registry/list_composite_splits"}
    )
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "compositea000000000000000000000": {
            "split_ids": unordered([device.id for device in splits_a]),
            "primary_id": primary_a.id,
        },
        "compositeb000000000000000000000": {
            "split_ids": unordered([device.id for device in splits_b]),
            "primary_id": None,
        },
    }


@pytest.mark.parametrize(
    ("payload_key", "payload_value"),
    [
        ("area_id", "12345A"),
        ("area_id", None),
        ("disabled_by", dr.DeviceEntryDisabler.USER),
        ("disabled_by", "user"),
        ("disabled_by", None),
        ("name_by_user", "Test Friendly Name"),
        ("name_by_user", None),
    ],
)
async def test_update_device(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    payload_key: str,
    payload_value: str | dr.DeviceEntryDisabler | None,
) -> None:
    """Test update entry."""
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)
    created_at = datetime.fromisoformat("2024-07-16T13:30:00.900075+00:00")
    freezer.move_to(created_at)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert not getattr(device, payload_key)

    modified_at = datetime.fromisoformat("2024-07-16T13:45:00.900075+00:00")
    freezer.move_to(modified_at)

    await client.send_json_auto_id(
        {
            "type": "config/device_registry/update",
            "device_id": device.id,
            payload_key: payload_value,
        }
    )

    msg = await client.receive_json()
    await hass.async_block_till_done()
    assert len(device_registry.devices) == 1

    [device] = device_registry.async_get_devices(
        identifiers={("bridgeid", "0123")},
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
    )

    assert msg["result"][payload_key] == payload_value
    assert getattr(device, payload_key) == payload_value
    for key, value in (
        ("created_at", created_at),
        ("modified_at", modified_at if payload_value is not None else created_at),
    ):
        assert msg["result"][key] == value.timestamp()
        assert getattr(device, key) == value

    assert isinstance(device.disabled_by, (dr.DeviceEntryDisabler, type(None)))


async def test_update_device_labels(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    device_registry: dr.DeviceRegistry,
    label_registry: lr.LabelRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update entry labels."""
    label_registry.async_create("label1")
    label_registry.async_create("label2")
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)
    created_at = datetime.fromisoformat("2024-07-16T13:30:00.900075+00:00")
    freezer.move_to(created_at)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert not device.labels
    modified_at = datetime.fromisoformat("2024-07-16T13:45:00.900075+00:00")
    freezer.move_to(modified_at)

    await client.send_json_auto_id(
        {
            "type": "config/device_registry/update",
            "device_id": device.id,
            "labels": ["label1", "label2"],
        }
    )

    msg = await client.receive_json()
    await hass.async_block_till_done()
    assert len(device_registry.devices) == 1

    [device] = device_registry.async_get_devices(
        identifiers={("bridgeid", "0123")},
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
    )

    assert msg["result"]["labels"] == unordered(["label1", "label2"])
    assert device.labels == {"label1", "label2"}
    for key, value in (
        ("created_at", created_at),
        ("modified_at", modified_at),
    ):
        assert msg["result"][key] == value.timestamp()
        assert getattr(device, key) == value


@pytest.mark.parametrize(
    ("labels", "expected_labels"),
    [
        pytest.param(["label1", "missing"], {"label1"}, id="strip_unknown"),
        pytest.param(["label1", "stale_label"], {"label1"}, id="strip_stale_resent"),
        pytest.param(["stale_label", "missing"], set(), id="strip_all_unknown"),
        pytest.param([], set(), id="remove_all"),
    ],
)
async def test_update_device_strips_unknown_labels(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    device_registry: dr.DeviceRegistry,
    label_registry: lr.LabelRegistry,
    labels: list[str],
    expected_labels: set[str],
) -> None:
    """Test labels not in the label registry are stripped on update.

    A stale label already stored on the device is cleaned up when the device
    is next saved, even if the client sends it back.
    """
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("bridgeid", "0123")},
    )
    # Seed a stale label via the helper layer, bypassing WS stripping
    device_registry.async_update_device(device.id, labels={"stale_label"})
    label_registry.async_create("label1")
    await client.send_json_auto_id(
        {
            "type": "config/device_registry/update",
            "device_id": device.id,
            "labels": labels,
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert set(msg["result"]["labels"]) == expected_labels
    assert device_registry.async_get(device.id).labels == expected_labels


async def test_update_device_unknown_device(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
) -> None:
    """Test updating an unknown device returns an error."""
    await client.send_json_auto_id(
        {
            "type": "config/device_registry/update",
            "device_id": "does_not_exist",
            "name_by_user": "Test Friendly Name",
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"
    assert msg["error"]["message"] == "Device not found"


@pytest.mark.parametrize("load_registries", [False])
async def test_update_device_composite(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    hass_storage: dict[str, Any],
) -> None:
    """Test updating a pre-migration composite device id is rejected."""
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)

    composite_id = "compositea000000000000000000000"
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                # Composite spanning two config entries; splitting it on load removes
                # the composite device, so composite_id no longer refers to a device
                _storage_device_v1_12(
                    composite_id,
                    [entry_1.entry_id, entry_2.entry_id],
                    entry_1.entry_id,
                    "a",
                ),
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    # pylint: disable-next=home-assistant-tests-registry-fixtures
    registry = dr.async_get(hass)
    assert registry.async_get(composite_id) is not None
    assert registry.async_get(composite_id, include_composite_devices=False) is None

    await client.send_json_auto_id(
        {
            "type": "config/device_registry/update",
            "device_id": composite_id,
            "name_by_user": "Test Friendly Name",
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "not_allowed"
    assert msg["error"]["message"] == "Cannot update a composite device"

    # The update was not fanned out to the underlying split devices
    for split in registry.async_get_devices_for_composite_device_id(composite_id):
        assert split.name_by_user is None


_DEPRECATION_WARNING = (
    "The websocket command config/device_registry/remove_config_entry is "
    "deprecated and will be removed in Home Assistant 2027.9"
)

# The new command and its deprecated alias share an implementation, so tests that
# apply to both are parametrized over them. The alias still takes config_entry_id,
# which must match the device's config entry, while the new command rejects it as an
# unknown key.
_REMOVE_DEVICE_COMMANDS = [
    pytest.param("config/device_registry/remove", False, id="remove"),
    pytest.param(
        "config/device_registry/remove_config_entry", True, id="remove_config_entry"
    ),
]


async def _send_remove_device(
    ws_client: MockHAClientWebSocket,
    command: str,
    device_id: str,
    config_entry_id: str,
) -> dict[str, Any]:
    """Send a device removal command and return the response."""
    message: dict[str, Any] = {"type": command, "device_id": device_id}
    if command == "config/device_registry/remove_config_entry":
        message["config_entry_id"] = config_entry_id
    await ws_client.send_json_auto_id(message)
    return await ws_client.receive_json()


@pytest.mark.parametrize(("command", "deprecated"), _REMOVE_DEVICE_COMMANDS)
async def test_remove_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    command: str,
    deprecated: bool,
) -> None:
    """Test removing a device via the command and its deprecated alias."""
    assert await async_setup_component(hass, DOMAIN, {})
    ws_client = await hass_ws_client(hass)

    can_remove = False

    async def async_remove_config_entry_device(
        hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.AnyDeviceEntry
    ) -> bool:
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

    device_entry_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    # Identifiers and connections are unique per config entry, so the two config
    # entries get separate devices even though they share a connection
    assert device_entry_1.id != device_entry.id
    assert device_entry.config_entries == {entry_2.entry_id}

    # Removal is rejected while async_remove_config_entry_device returns False
    response = await _send_remove_device(
        ws_client, command, device_entry.id, entry_2.entry_id
    )

    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"

    # Make async_remove_config_entry_device return True
    can_remove = True

    # The device is removed
    response = await _send_remove_device(
        ws_client, command, device_entry.id, entry_2.entry_id
    )

    assert response["success"]
    assert response["result"] is None

    assert not device_registry.async_get(device_entry.id)

    # The device belonging to the other config entry is untouched
    assert device_registry.async_get(device_entry_1.id).config_entries == {
        entry_1.entry_id
    }

    # Only the deprecated alias logs a deprecation warning
    assert (_DEPRECATION_WARNING in caplog.text) is deprecated


async def test_remove_device_fails(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a device failing cases."""
    assert await async_setup_component(hass, DOMAIN, {})
    ws_client = await hass_ws_client(hass)

    async def async_remove_config_entry_device(
        hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.AnyDeviceEntry
    ) -> bool:
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

    device_entry_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    device_entry_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    device_entry_3 = device_registry.async_get_or_create(
        config_entry_id=entry_3.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    # Identifiers and connections are unique per config entry, so each config entry
    # gets its own device even though they share a connection
    assert device_entry_1.config_entries == {entry_1.entry_id}
    assert device_entry_2.config_entries == {entry_2.entry_id}
    assert device_entry_3.config_entries == {entry_3.entry_id}

    fake_device_id = "abc123"
    assert device_entry_3.id != fake_device_id

    # Try removing a device which does not exist
    response = await ws_client.remove_device(fake_device_id)

    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert response["error"]["message"] == "Unknown device"

    # Try removing a device whose config entry does not support device removal
    response = await ws_client.remove_device(device_entry_1.id)

    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert (
        response["error"]["message"] == "Config entry does not support device removal"
    )

    # Removing a device whose config entry supports removal removes the device
    response = await ws_client.remove_device(device_entry_2.id)

    assert response["success"]
    assert response["result"] is None
    assert not device_registry.async_get(device_entry_2.id)

    # Try removing a device whose integration can't be loaded
    response = await ws_client.remove_device(device_entry_3.id)

    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert response["error"]["message"] == "Integration not found"


async def test_remove_device_if_integration_removes(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a device.

    Should not error when the integration removes the device itself.
    """
    assert await async_setup_component(hass, DOMAIN, {})
    ws_client = await hass_ws_client(hass)

    can_remove = False

    async def async_remove_config_entry_device(
        hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.AnyDeviceEntry
    ) -> bool:
        if can_remove:
            device_registry.async_remove_device(device_entry.id)
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

    device_entry_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    # Identifiers and connections are unique per config entry, so the two config
    # entries get separate devices even though they share a connection
    assert device_entry_1.id != device_entry.id
    assert device_entry.config_entries == {entry_2.entry_id}

    # Removal is rejected while async_remove_config_entry_device returns False
    response = await ws_client.remove_device(device_entry.id)

    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"

    # Make async_remove_config_entry_device return True
    can_remove = True

    # The device is removed by the integration itself
    response = await ws_client.remove_device(device_entry.id)

    assert response["success"]
    assert response["result"] is None

    assert not device_registry.async_get(device_entry.id)

    # The device belonging to the other config entry is untouched
    assert device_registry.async_get(device_entry_1.id).config_entries == {
        entry_1.entry_id
    }


@pytest.mark.parametrize(("command", "deprecated"), _REMOVE_DEVICE_COMMANDS)
@pytest.mark.parametrize("load_registries", [False])
async def test_remove_device_composite(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    command: str,
    deprecated: bool,
) -> None:
    """Test removing a pre-migration composite device id fails."""
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)

    composite_id = "compositea000000000000000000000"
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                # Composite spanning two config entries; splitting it on load removes
                # the composite device, so composite_id no longer refers to a device
                _storage_device_v1_12(
                    composite_id,
                    [entry_1.entry_id, entry_2.entry_id],
                    entry_1.entry_id,
                    "a",
                ),
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    # pylint: disable-next=home-assistant-tests-registry-fixtures
    registry = dr.async_get(hass)
    assert registry.async_get(composite_id) is not None
    assert registry.async_get(composite_id, include_composite_devices=False) is None

    response = await _send_remove_device(
        client, command, composite_id, entry_1.entry_id
    )

    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert response["error"]["message"] == "Cannot remove a composite device"
    assert (_DEPRECATION_WARNING in caplog.text) is deprecated


async def test_remove_config_entry_from_device_deprecated_config_entry_mismatch(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the deprecated alias fails if config_entry_id is not the device's."""
    assert await async_setup_component(hass, DOMAIN, {})
    ws_client = await hass_ws_client(hass)

    async def async_remove_config_entry_device(
        hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.AnyDeviceEntry
    ) -> bool:
        return True

    mock_integration(
        hass,
        MockModule(
            "comp1", async_remove_config_entry_device=async_remove_config_entry_device
        ),
    )

    entry_1 = MockConfigEntry(domain="comp1", title="Test 1", source="bla")
    entry_1.supports_remove_device = True
    entry_1.add_to_hass(hass)

    # A second, unrelated config entry
    entry_2 = MockConfigEntry(domain="comp1", title="Test 2", source="bla")
    entry_2.supports_remove_device = True
    entry_2.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    # Passing a config entry which is not the device's fails, device is untouched
    response = await _send_remove_device(
        ws_client,
        "config/device_registry/remove_config_entry",
        device_entry.id,
        entry_2.entry_id,
    )

    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert response["error"]["message"] == "Config entry not in device"
    assert device_registry.async_get(device_entry.id) is not None

    # Passing the device's own config entry removes the device
    response = await _send_remove_device(
        ws_client,
        "config/device_registry/remove_config_entry",
        device_entry.id,
        entry_1.entry_id,
    )

    assert response["success"]
    assert response["result"] is None
    assert not device_registry.async_get(device_entry.id)


async def test_list_linked_devices(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test listing devices sharing a connection or identifier."""
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)
    entry_3 = MockConfigEntry()
    entry_3.add_to_hass(hass)

    mac = (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")

    # device_1 shares its identifier with device_2 and its connection with device_3
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        connections={mac},
        identifiers={("bridgeid", "0123")},
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        identifiers={("bridgeid", "0123")},
    )
    device_3 = device_registry.async_get_or_create(
        config_entry_id=entry_3.entry_id,
        connections={mac},
    )
    # device_4 shares nothing with the others
    device_4 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        identifiers={("bridgeid", "9999")},
    )
    assert len({device_1.id, device_2.id, device_3.id, device_4.id}) == 4

    async def list_linked(device_id: str) -> dict:
        await client.send_json_auto_id(
            {
                "type": "config/device_registry/list_linked_devices",
                "device_id": device_id,
            }
        )
        return await client.receive_json()

    # device_1 is linked to both device_2 (identifier) and device_3 (connection)
    msg = await list_linked(device_1.id)
    assert msg["success"]
    assert msg["result"]["linked_devices"] == unordered([device_2.id, device_3.id])

    # device_2 and device_3 each only share with device_1, not with each other
    msg = await list_linked(device_2.id)
    assert msg["result"]["linked_devices"] == [device_1.id]

    msg = await list_linked(device_3.id)
    assert msg["result"]["linked_devices"] == [device_1.id]

    # device_4 has no linked devices
    msg = await list_linked(device_4.id)
    assert msg["result"]["linked_devices"] == []


async def test_list_linked_devices_unknown_device(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
) -> None:
    """Test listing linked devices for an unknown device returns an error."""
    await client.send_json_auto_id(
        {
            "type": "config/device_registry/list_linked_devices",
            "device_id": "does_not_exist",
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"
    assert msg["error"]["message"] == "Device not found"


def _create_parent_and_child(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    *,
    domain: str = "test",
) -> tuple[MockConfigEntry, dr.DeviceEntry, dr.ChildDeviceEntry]:
    """Create a config entry with a parent device and one child device."""
    entry = MockConfigEntry(domain=domain, title="Test")
    entry.add_to_hass(hass)
    parent = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(domain, "strip")},
        name="Power strip",
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=entry.entry_id,
        identifiers={(domain, "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    return entry, parent, child_device


async def test_list_devices_with_child_devices(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test child devices are included in the device list."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)
    entry, parent, child_device = _create_parent_and_child(hass, device_registry)

    await client.send_json_auto_id({"type": "config/device_registry/list"})
    msg = await client.receive_json()

    assert msg["result"] == [
        {
            "area_id": None,
            "config_entries": [entry.entry_id],
            "config_entries_subentries": {entry.entry_id: [None]},
            "config_entry_id": entry.entry_id,
            "config_subentry_id": None,
            "configuration_url": None,
            "connections": [],
            "created_at": parent.created_at.timestamp(),
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "id": parent.id,
            "identifiers": [["test", "strip"]],
            "labels": [],
            "manufacturer": None,
            "model": None,
            "model_id": None,
            "modified_at": parent.modified_at.timestamp(),
            "name_by_user": None,
            "name": "Power strip",
            "parent_device_id": None,
            "primary_config_entry": entry.entry_id,
            "serial_number": None,
            "sw_version": None,
            "via_device_id": None,
        },
        {
            "area_id": None,
            "config_entry_id": entry.entry_id,
            "config_subentry_id": None,
            "created_at": child_device.created_at.timestamp(),
            "disabled_by": None,
            "id": child_device.id,
            "identifiers": [["test", "strip_outlet_1"]],
            "labels": [],
            "modified_at": child_device.modified_at.timestamp(),
            "name_by_user": None,
            "name": "Outlet 1",
            "parent_device_id": parent.id,
        },
    ]


@pytest.mark.parametrize(
    ("payload_key", "payload_value", "expected_registry_value"),
    [
        pytest.param("area_id", "garden", "garden", id="area_id"),
        pytest.param("labels", ["label1"], {"label1"}, id="labels"),
        pytest.param("name_by_user", "Garden lamp", "Garden lamp", id="name_by_user"),
        pytest.param(
            "disabled_by", "user", dr.DeviceEntryDisabler.USER, id="disabled_by"
        ),
    ],
)
async def test_update_child_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    label_registry: lr.LabelRegistry,
    payload_key: str,
    payload_value: Any,
    expected_registry_value: Any,
) -> None:
    """Test updating a child device through the websocket API."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)
    label_registry.async_create("label1")
    _, _, child_device = _create_parent_and_child(hass, device_registry)

    await client.send_json_auto_id(
        {
            "type": "config/device_registry/update",
            "device_id": child_device.id,
            payload_key: payload_value,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"][payload_key] == payload_value
    assert msg["result"]["parent_device_id"] == child_device.parent_device_id

    # The update reached the registry entry, not just the websocket response
    updated_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert updated_child is not None
    assert getattr(updated_child, payload_key) == expected_registry_value


async def test_update_child_device_area_round_trip(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test overriding and re-inheriting a child device area via the API."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)
    _, parent, child_device = _create_parent_and_child(hass, device_registry)
    device_registry.async_update_device(parent.id, area_id="garage")

    await client.send_json_auto_id(
        {
            "type": "config/device_registry/update",
            "device_id": child_device.id,
            "area_id": "garden",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["area_id"] == "garden"

    # Clearing the area restores inheriting the parent's area
    await client.send_json_auto_id(
        {
            "type": "config/device_registry/update",
            "device_id": child_device.id,
            "area_id": None,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["area_id"] is None
    updated_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert updated_child is not None
    assert dr.async_get_effective_area_id(hass, updated_child) == "garage"


async def test_remove_config_entry_from_child_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a child device via the websocket API."""
    assert await async_setup_component(hass, DOMAIN, {})
    ws_client = await hass_ws_client(hass)

    can_remove = False
    removed_devices: list[str] = []

    async def async_remove_config_entry_device(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device_entry: dr.AnyDeviceEntry,
    ) -> bool:
        removed_devices.append(device_entry.id)
        return can_remove

    mock_integration(
        hass,
        MockModule(
            "comp1", async_remove_config_entry_device=async_remove_config_entry_device
        ),
    )
    entry, parent, child_device = _create_parent_and_child(
        hass, device_registry, domain="comp1"
    )
    entry.supports_remove_device = True

    # Rejected by the integration
    response = await ws_client.remove_device(child_device.id)
    assert not response["success"]
    assert response["error"]["code"] == "home_assistant_error"
    assert removed_devices == [child_device.id]

    can_remove = True
    removed_devices.clear()

    # The integration hook receives the child device entry
    response = await ws_client.remove_device(child_device.id)
    assert response["success"]
    assert removed_devices == [child_device.id]
    assert device_registry.async_get(child_device.id) is None
    assert device_registry.async_get(parent.id) is not None


async def test_remove_config_entry_from_parent_with_children(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a parent device consults the hook once and cascades."""
    assert await async_setup_component(hass, DOMAIN, {})
    ws_client = await hass_ws_client(hass)

    consulted_devices: list[str] = []

    async def async_remove_config_entry_device(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device_entry: dr.AnyDeviceEntry,
    ) -> bool:
        consulted_devices.append(device_entry.id)
        return True

    mock_integration(
        hass,
        MockModule(
            "comp1", async_remove_config_entry_device=async_remove_config_entry_device
        ),
    )
    entry, parent, child_device = _create_parent_and_child(
        hass, device_registry, domain="comp1"
    )
    entry.supports_remove_device = True

    response = await ws_client.remove_device(parent.id)
    assert response["success"]
    # The hook is consulted once, with the parent; child devices cascade
    assert consulted_devices == [parent.id]
    assert device_registry.async_get(parent.id) is None
    assert device_registry.async_get(child_device.id) is None


async def test_list_linked_devices_child_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a child device is never reported as linked.

    A child shares its parent's per-config-entry identifier namespace, so even
    when a main device of another config entry carries the same identifier the
    child must still yield an empty result.
    """
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)
    _, _, child_device = _create_parent_and_child(hass, device_registry)

    # A main device of another config entry that shares the child's identifier
    # would be surfaced if children were matched like main devices; it must not.
    other_entry = MockConfigEntry()
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
    )
    assert other_device.identifiers == child_device.identifiers

    await client.send_json_auto_id(
        {
            "type": "config/device_registry/list_linked_devices",
            "device_id": child_device.id,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"linked_devices": []}
