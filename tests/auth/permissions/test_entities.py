"""Tests for entity permissions."""
from homeassistant.auth.permissions.entities import (
    ENTITY_POLICY_SCHEMA,
    compile_entities,
)
from homeassistant.auth.permissions.models import PermissionLookup
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_registry import RegistryEntry

from tests.common import mock_device_registry, mock_registry


def test_entities_none():
    """Test entity ID policy."""
    policy = None
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is False


def test_entities_empty():
    """Test entity ID policy."""
    policy = {}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is False


def test_entities_false():
    """Test entity ID policy."""
    policy = False
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is False


def test_entities_true():
    """Test entity ID policy."""
    policy = True
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is True


def test_entities_domains_true():
    """Test entity ID policy."""
    policy = {"domains": True}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is True


def test_entities_domains_domain_true():
    """Test entity ID policy."""
    policy = {"domains": {"light": True}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("switch.kitchen", "read") is False


def test_entities_domains_domain_false():
    """Test entity ID policy."""
    policy = {"domains": {"light": False}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is False


def test_entities_entity_ids_true():
    """Test entity ID policy."""
    policy = {"entity_ids": True}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is True


def test_entities_entity_ids_false():
    """Test entity ID policy."""
    policy = {"entity_ids": False}
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is False


def test_entities_entity_ids_entity_id_true():
    """Test entity ID policy."""
    policy = {"entity_ids": {"light.kitchen": True}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("switch.kitchen", "read") is False


def test_entities_entity_ids_entity_id_false():
    """Test entity ID policy."""
    policy = {"entity_ids": {"light.kitchen": False}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is False


def test_entities_control_only():
    """Test policy granting control only."""
    policy = {"entity_ids": {"light.kitchen": {"read": True}}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is False
    assert compiled("light.kitchen", "edit") is False


def test_entities_read_control():
    """Test policy granting control only."""
    policy = {"domains": {"light": {"read": True, "control": True}}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is True
    assert compiled("light.kitchen", "edit") is False


def test_entities_all_allow():
    """Test policy allowing all entities."""
    policy = {"all": True}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is True
    assert compiled("switch.kitchen", "read") is True


def test_entities_all_read():
    """Test policy applying read to all entities."""
    policy = {"all": {"read": True}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is False
    assert compiled("switch.kitchen", "read") is True


def test_entities_all_control():
    """Test entity ID policy applying control to all."""
    policy = {"all": {"control": True}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is False
    assert compiled("light.kitchen", "control") is True
    assert compiled("switch.kitchen", "read") is False
    assert compiled("switch.kitchen", "control") is True


def test_entities_device_id_boolean(hass):
    """Test entity ID policy applying control on device id."""
    entity_registry = mock_registry(
        hass,
        {
            "test_domain.allowed": RegistryEntry(
                entity_id="test_domain.allowed",
                unique_id="1234",
                platform="test_platform",
                device_id="mock-allowed-dev-id",
            ),
            "test_domain.not_allowed": RegistryEntry(
                entity_id="test_domain.not_allowed",
                unique_id="5678",
                platform="test_platform",
                device_id="mock-not-allowed-dev-id",
            ),
        },
    )
    device_registry = mock_device_registry(hass)

    policy = {"device_ids": {"mock-allowed-dev-id": {"read": True}}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(
        [policy], PermissionLookup(entity_registry, device_registry)
    )
    assert compiled("test_domain.allowed", "read") is True
    assert compiled("test_domain.allowed", "control") is False
    assert compiled("test_domain.not_allowed", "read") is False
    assert compiled("test_domain.not_allowed", "control") is False


def test_entities_areas_true():
    """Test entity ID policy for areas."""
    policy = {"area_ids": True}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities([policy], None)
    assert compiled("light.kitchen", "read") is True


def test_entities_areas_area_true(hass):
    """Test entity ID policy for areas with specific area."""
    entity_registry = mock_registry(
        hass,
        {
            "light.kitchen": RegistryEntry(
                entity_id="light.kitchen",
                unique_id="1234",
                platform="test_platform",
                device_id="mock-dev-id",
            ),
            "light.livingroom": RegistryEntry(
                entity_id="light.livingroom",
                unique_id="5678",
                platform="test_platform",
                area_id="mock-area-id-2",
            ),
        },
    )
    device_registry = mock_device_registry(
        hass, {"mock-dev-id": DeviceEntry(id="mock-dev-id", area_id="mock-area-id")}
    )

    policy = {
        "area_ids": {
            "mock-area-id": {"read": True, "control": True},
            "mock-area-id-2": {"edit": True},
        }
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(
        [policy], PermissionLookup(entity_registry, device_registry)
    )
    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is True
    assert compiled("light.kitchen", "edit") is False
    assert compiled("switch.kitchen", "read") is False
    assert compiled("light.livingroom", "read") is False
    assert compiled("light.livingroom", "control") is False
    assert compiled("light.livingroom", "edit") is True


def test_entities_entity_id_exception(hass):
    """Test entity ID policy with exceptions for a specific entity id."""
    entity_registry = mock_registry(
        hass,
        {
            "light.kitchen": RegistryEntry(
                entity_id="light.kitchen",
                unique_id="1234",
                platform="test_platform",
                device_id="mock-dev-id",
            ),
            "light.kitchen_secondary": RegistryEntry(
                entity_id="light.kitchen_secondary",
                unique_id="5678",
                platform="test_platform",
                device_id="mock-dev-id",
            ),
            "light.kitchen_ternary": RegistryEntry(
                entity_id="light.kitchen_ternary",
                unique_id="9012",
                platform="test_platform",
                device_id="mock-dev-id",
            ),
        },
    )
    device_registry = mock_device_registry(
        hass, {"mock-dev-id": DeviceEntry(id="mock-dev-id", area_id="mock-area-id")}
    )

    policy = {
        "area_ids": {"mock-area-id": {"read": True, "control": True}},
        "entity_ids": {"light.kitchen_secondary": {"read": False}},
    }

    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(
        [policy], PermissionLookup(entity_registry, device_registry)
    )

    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is True
    assert compiled("light.kitchen", "edit") is False
    assert compiled("light.kitchen_secondary", "read") is False
    assert compiled("light.kitchen_secondary", "control") is True
    assert compiled("light.kitchen_secondary", "edit") is False
    assert compiled("light.kitchen_ternary", "read") is True
    assert compiled("light.kitchen_ternary", "control") is True
    assert compiled("light.kitchen_ternary", "edit") is False
    assert compiled("switch.kitchen", "read") is False


def test_entities_entity_id_exception_with_boolean(hass):
    """Test entity ID policy with exceptions for a specific entity id."""
    entity_registry = mock_registry(
        hass,
        {
            "light.kitchen": RegistryEntry(
                entity_id="light.kitchen",
                unique_id="1234",
                platform="test_platform",
                device_id="mock-dev-id",
            ),
            "light.kitchen_secondary": RegistryEntry(
                entity_id="light.kitchen_secondary",
                unique_id="5678",
                platform="test_platform",
                device_id="mock-dev-id",
            ),
        },
    )
    device_registry = mock_device_registry(
        hass, {"mock-dev-id": DeviceEntry(id="mock-dev-id", area_id="mock-area-id")}
    )

    policy = {
        "area_ids": True,
        "entity_ids": {"light.kitchen_secondary": {"read": False}},
    }

    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(
        [policy], PermissionLookup(entity_registry, device_registry)
    )

    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is True
    assert compiled("light.kitchen", "edit") is True
    assert compiled("light.kitchen_secondary", "read") is False
    assert compiled("light.kitchen_secondary", "control") is True
    assert compiled("light.kitchen_secondary", "edit") is True
