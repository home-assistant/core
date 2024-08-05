"""Tests for entity permissions."""

import pytest
import voluptuous as vol

from homeassistant.auth.permissions.entities import (
    ENTITY_POLICY_SCHEMA,
    compile_entities,
)
from homeassistant.auth.permissions.models import PermissionLookup
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_registry import RegistryEntry

from tests.common import mock_device_registry, mock_registry


def test_entities_none() -> None:
    """Test entity ID policy."""
    policy = None
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is False


def test_entities_empty() -> None:
    """Test entity ID policy."""
    policy = {}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is False


def test_entities_false() -> None:
    """Test entity ID policy."""
    policy = False
    with pytest.raises(vol.Invalid):
        ENTITY_POLICY_SCHEMA(policy)


def test_entities_true() -> None:
    """Test entity ID policy."""
    policy = True
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is True


def test_entities_domains_true() -> None:
    """Test entity ID policy."""
    policy = {"domains": True}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is True


def test_entities_domains_domain_true() -> None:
    """Test entity ID policy."""
    policy = {"domains": {"light": True}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("switch.kitchen", "read") is False


def test_entities_domains_domain_false() -> None:
    """Test entity ID policy."""
    policy = {"domains": {"light": False}}
    with pytest.raises(vol.Invalid):
        ENTITY_POLICY_SCHEMA(policy)


def test_entities_entity_ids_true() -> None:
    """Test entity ID policy."""
    policy = {"entity_ids": True}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is True


def test_entities_entity_ids_false() -> None:
    """Test entity ID policy."""
    policy = {"entity_ids": False}
    with pytest.raises(vol.Invalid):
        ENTITY_POLICY_SCHEMA(policy)


def test_entities_entity_ids_entity_id_true() -> None:
    """Test entity ID policy."""
    policy = {"entity_ids": {"light.kitchen": True}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("switch.kitchen", "read") is False


def test_entities_entity_ids_entity_id_false() -> None:
    """Test entity ID policy."""
    policy = {"entity_ids": {"light.kitchen": False}}
    with pytest.raises(vol.Invalid):
        ENTITY_POLICY_SCHEMA(policy)


def test_entities_control_only() -> None:
    """Test policy granting control only."""
    policy = {"entity_ids": {"light.kitchen": {"read": True}}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is False
    assert compiled("light.kitchen", "edit") is False


def test_entities_read_control() -> None:
    """Test policy granting control only."""
    policy = {"domains": {"light": {"read": True, "control": True}}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is True
    assert compiled("light.kitchen", "edit") is False


def test_entities_all_allow() -> None:
    """Test policy allowing all entities."""
    policy = {"all": True}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is True
    assert compiled("switch.kitchen", "read") is True


def test_entities_all_read() -> None:
    """Test policy applying read to all entities."""
    policy = {"all": {"read": True}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is False
    assert compiled("switch.kitchen", "read") is True


def test_entities_all_control() -> None:
    """Test entity ID policy applying control to all."""
    policy = {"all": {"control": True}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is False
    assert compiled("light.kitchen", "control") is True
    assert compiled("switch.kitchen", "read") is False
    assert compiled("switch.kitchen", "control") is True


def test_entities_device_id_boolean(hass: HomeAssistant) -> None:
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
        policy, PermissionLookup(entity_registry, device_registry)
    )
    assert compiled("test_domain.allowed", "read") is True
    assert compiled("test_domain.allowed", "control") is False
    assert compiled("test_domain.not_allowed", "read") is False
    assert compiled("test_domain.not_allowed", "control") is False


def test_entities_areas_true() -> None:
    """Test entity ID policy for areas."""
    policy = {"area_ids": True}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy, None)
    assert compiled("light.kitchen", "read") is True


def test_entities_areas_area_true(hass: HomeAssistant) -> None:
    """Test entity ID policy for areas with specific area."""
    entity_registry = mock_registry(
        hass,
        {
            "light.kitchen": RegistryEntry(
                entity_id="light.kitchen",
                unique_id="1234",
                platform="test_platform",
                device_id="mock-dev-id",
            )
        },
    )
    device_registry = mock_device_registry(
        hass, {"mock-dev-id": DeviceEntry(id="mock-dev-id", area_id="mock-area-id")}
    )

    policy = {"area_ids": {"mock-area-id": {"read": True, "control": True}}}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(
        policy, PermissionLookup(entity_registry, device_registry)
    )
    assert compiled("light.kitchen", "read") is True
    assert compiled("light.kitchen", "control") is True
    assert compiled("light.kitchen", "edit") is False
    assert compiled("switch.kitchen", "read") is False
