"""Tests for merged policies."""

from homeassistant.auth.permissions.entities import (
    ENTITY_POLICY_SCHEMA,
    compile_entities,
)
from homeassistant.auth.permissions.models import PermissionLookup
from homeassistant.helpers.entity_registry import RegistryEntry

from tests.common import mock_device_registry, mock_registry


def test_merging_disjoint_additives(hass):
    """Test merging two additive-only policies."""
    entity_registry = mock_registry(
        hass,
        {
            "test_domain.one": RegistryEntry(
                entity_id="test_domain.one",
                unique_id="1234",
                platform="test_platform",
                device_id="mock-dev-id-one",
            ),
            "test_domain.two": RegistryEntry(
                entity_id="test_domain.two",
                unique_id="5678",
                platform="test_platform",
                device_id="mock-dev-id-two",
            ),
        },
    )

    device_registry = mock_device_registry(hass)

    policy1 = {"device_ids": {"mock-dev-id-one": {"read": True}}}
    policy2 = {"device_ids": {"mock-dev-id-two": {"edit": True}}}

    ENTITY_POLICY_SCHEMA(policy1)
    ENTITY_POLICY_SCHEMA(policy2)

    compiled = compile_entities(
        [policy1, policy2], PermissionLookup(entity_registry, device_registry)
    )
    assert compiled("test_domain.one", "read") is True
    assert compiled("test_domain.one", "edit") is False
    assert compiled("test_domain.two", "read") is False
    assert compiled("test_domain.two", "edit") is True


def test_merging_with_all_false(hass):
    """Test merging a policy with an all-false policy. Codepath drops all-false policies."""
    entity_registry = mock_registry(
        hass,
        {
            "test_domain.one": RegistryEntry(
                entity_id="test_domain.one",
                unique_id="1234",
                platform="test_platform",
                device_id="mock-dev-id-one",
            ),
            "test_domain.two": RegistryEntry(
                entity_id="test_domain.two",
                unique_id="5678",
                platform="test_platform",
                device_id="mock-dev-id-two",
            ),
        },
    )

    device_registry = mock_device_registry(hass)

    policy1 = {"device_ids": {"mock-dev-id-one": {"read": True}}}
    policy2 = {"all": False}

    ENTITY_POLICY_SCHEMA(policy1)
    ENTITY_POLICY_SCHEMA(policy2)

    compiled = compile_entities(
        [policy1, policy2], PermissionLookup(entity_registry, device_registry)
    )
    assert compiled("test_domain.one", "read") is True
    assert compiled("test_domain.one", "edit") is False
    assert compiled("test_domain.two", "read") is False
    assert compiled("test_domain.two", "edit") is False


def test_merging_with_conflicting_policies(hass):
    """Test merging two policies with conflicting results; positive sohuld win."""
    entity_registry = mock_registry(
        hass,
        {
            "test_domain.one": RegistryEntry(
                entity_id="test_domain.one",
                unique_id="1234",
                platform="test_platform",
                device_id="mock-dev-id-one",
            ),
            "test_domain.two": RegistryEntry(
                entity_id="test_domain.two",
                unique_id="5678",
                platform="test_platform",
                device_id="mock-dev-id-two",
            ),
        },
    )

    device_registry = mock_device_registry(hass)

    policy1 = {"device_ids": {"mock-dev-id-one": {"read": True}}}
    policy2 = {"device_ids": {"mock-dev-id-one": {"read": False}}}

    ENTITY_POLICY_SCHEMA(policy1)
    ENTITY_POLICY_SCHEMA(policy2)

    compiled = compile_entities(
        [policy1, policy2], PermissionLookup(entity_registry, device_registry)
    )
    assert compiled("test_domain.one", "read") is True
    assert compiled("test_domain.one", "edit") is False
    assert compiled("test_domain.two", "read") is False
    assert compiled("test_domain.two", "edit") is False


def test_merging_with_single_policy(hass):
    """Test merging a single policy; codepath optimizes this to return that poclicy function."""
    entity_registry = mock_registry(
        hass,
        {
            "test_domain.one": RegistryEntry(
                entity_id="test_domain.one",
                unique_id="1234",
                platform="test_platform",
                device_id="mock-dev-id-one",
            ),
        },
    )

    device_registry = mock_device_registry(hass)

    policy1 = {"device_ids": {"mock-dev-id-one": {"read": True}}}

    ENTITY_POLICY_SCHEMA(policy1)

    compiled = compile_entities(
        [policy1], PermissionLookup(entity_registry, device_registry)
    )
    assert compiled("test_domain.one", "read") is True
    assert compiled("test_domain.one", "edit") is False

    policy2 = {"all": False}

    ENTITY_POLICY_SCHEMA(policy2)

    compiled2 = compile_entities(
        [policy2], PermissionLookup(entity_registry, device_registry)
    )
    assert compiled2("test_domain.one", "read") is False
    assert compiled2("test_domain.one", "edit") is False

    policy3 = {"all": True}

    ENTITY_POLICY_SCHEMA(policy3)

    compiled3 = compile_entities(
        [policy3], PermissionLookup(entity_registry, device_registry)
    )
    assert compiled3("test_domain.one", "read") is True
    assert compiled3("test_domain.one", "edit") is True


def test_merging_with_conflicting_non_additive_policies(hass):
    """
    Test merging a non-additive policy with a deny that covers a grant in another policy.

    Ensure deny doesn't affect that grant.
    """
    entity_registry = mock_registry(
        hass,
        {
            "test_domain.one": RegistryEntry(
                entity_id="test_domain.one",
                unique_id="1234",
                platform="test_platform",
                device_id="mock-dev-id-one",
            ),
            "test_domain.two": RegistryEntry(
                entity_id="test_domain.two",
                unique_id="5678",
                platform="test_platform",
                device_id="mock-dev-id-two",
            ),
            "test_domain.three": RegistryEntry(
                entity_id="test_domain.three",
                unique_id="8765",
                platform="test_platform",
                device_id="mock-dev-id-one",
            ),
        },
    )

    device_registry = mock_device_registry(hass)

    policy1 = {
        "device_ids": {"mock-dev-id-one": {"read": True}},
        "entity_ids": {"test_domain.one": False},
    }
    policy2 = {
        "device_ids": {"mock-dev-id-one": {"edit": True}},
        "all": {"control": True},
    }

    ENTITY_POLICY_SCHEMA(policy1)
    ENTITY_POLICY_SCHEMA(policy2)

    compiled = compile_entities(
        [policy1, policy2], PermissionLookup(entity_registry, device_registry)
    )

    assert compiled("test_domain.one", "read") is False
    assert compiled("test_domain.one", "edit") is True
    assert compiled("test_domain.one", "control") is True
    assert compiled("test_domain.two", "read") is False
    assert compiled("test_domain.two", "edit") is False
    assert compiled("test_domain.two", "control") is True
    assert compiled("test_domain.three", "read") is True
    assert compiled("test_domain.three", "edit") is True
    assert compiled("test_domain.two", "control") is True
