"""Tests for Overkiz entity."""

from unittest.mock import Mock

import pytest

from homeassistant.components.overkiz.entity import OverkizEntity


def _create_mock_device(device_url: str, place_oid: str, label: str) -> Mock:
    """Create a mock device."""
    device = Mock()
    device.device_url = device_url
    device.place_oid = place_oid
    device.label = label
    device.available = True
    device.states = []
    device.widget = Mock(value="TestWidget")
    device.controllable_name = "test:Component"
    return device


def _create_mock_entity(device: Mock, all_devices: list[Mock]) -> Mock:
    """Create a mock entity with the given device and coordinator data."""
    entity = Mock(spec=OverkizEntity)
    entity.device = device
    entity.device_url = device.device_url
    entity.base_device_url = device.device_url.split("#")[0]
    entity.coordinator = Mock()
    entity.coordinator.data = {d.device_url: d for d in all_devices}
    entity._get_sibling_devices = lambda: [
        d
        for d in all_devices
        if d.device_url != device.device_url
        and d.device_url.startswith(f"{entity.base_device_url}#")
    ]
    return entity


@pytest.mark.parametrize(
    ("place_oids", "expected"),
    [
        (["place-a", "place-b"], True),
        (["place-a", "place-a"], False),
    ],
    ids=["different_place_oids", "same_place_oids"],
)
def test_has_siblings_with_different_place_oid(
    place_oids: list[str], expected: bool
) -> None:
    """Test detection of siblings with different placeOIDs."""
    devices = [
        _create_mock_device("io://gateway/123#1", place_oids[0], "Device 1"),
        _create_mock_device("io://gateway/123#2", place_oids[1], "Device 2"),
    ]
    entity = _create_mock_entity(devices[0], devices)

    result = OverkizEntity._has_siblings_with_different_place_oid(entity)

    assert result is expected


@pytest.mark.parametrize(
    ("device_index", "expected"),
    [
        (0, True),
        (1, False),
    ],
    ids=["lowest_index_is_main", "higher_index_not_main"],
)
def test_is_main_device_for_place_oid(device_index: int, expected: bool) -> None:
    """Test main device detection for placeOID group."""
    devices = [
        _create_mock_device("io://gateway/123#1", "place-a", "Device 1"),
        _create_mock_device("io://gateway/123#4", "place-a", "Device 4"),
    ]
    entity = _create_mock_entity(devices[device_index], devices)

    result = OverkizEntity._is_main_device_for_place_oid(entity)

    assert result is expected


def test_get_via_device_id_sub_device_links_to_main() -> None:
    """Test sub-device links to main actuator with placeOID grouping."""
    devices = [
        _create_mock_device("io://gateway/123#1", "place-a", "Actuator"),
        _create_mock_device("io://gateway/123#2", "place-b", "Zone"),
    ]
    entity = _create_mock_entity(devices[1], devices)
    entity.executor = Mock()
    entity.executor.get_gateway_id = Mock(return_value="gateway-id")

    result = OverkizEntity._get_via_device_id(entity, use_place_oid_grouping=True)

    assert result == "io://gateway/123#place-a"


def test_get_via_device_id_main_device_links_to_gateway() -> None:
    """Test main device (#1) links to gateway."""
    devices = [
        _create_mock_device("io://gateway/123#1", "place-a", "Actuator"),
    ]
    entity = _create_mock_entity(devices[0], devices)
    entity.executor = Mock()
    entity.executor.get_gateway_id = Mock(return_value="gateway-id")

    result = OverkizEntity._get_via_device_id(entity, use_place_oid_grouping=True)

    assert result == "gateway-id"
