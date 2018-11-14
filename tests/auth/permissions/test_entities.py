"""Tests for entity permissions."""
import pytest
import voluptuous as vol

from homeassistant.auth.permissions.entities import (
  compile_entities, ENTITY_POLICY_SCHEMA)


def test_entities_none():
    """Test entity ID policy."""
    policy = None
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is False


def test_entities_empty():
    """Test entity ID policy."""
    policy = {}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is False


def test_entities_false():
    """Test entity ID policy."""
    policy = False
    with pytest.raises(vol.Invalid):
        ENTITY_POLICY_SCHEMA(policy)


def test_entities_true():
    """Test entity ID policy."""
    policy = True
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is True


def test_entities_domains_true():
    """Test entity ID policy."""
    policy = {
        'domains': True
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is True


def test_entities_domains_domain_true():
    """Test entity ID policy."""
    policy = {
        'domains': {
            'light': True
        }
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is True
    assert compiled('switch.kitchen', ('read',)) is False


def test_entities_domains_domain_false():
    """Test entity ID policy."""
    policy = {
        'domains': {
            'light': False
        }
    }
    with pytest.raises(vol.Invalid):
        ENTITY_POLICY_SCHEMA(policy)


def test_entities_entity_ids_true():
    """Test entity ID policy."""
    policy = {
        'entity_ids': True
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is True


def test_entities_entity_ids_false():
    """Test entity ID policy."""
    policy = {
        'entity_ids': False
    }
    with pytest.raises(vol.Invalid):
        ENTITY_POLICY_SCHEMA(policy)


def test_entities_entity_ids_entity_id_true():
    """Test entity ID policy."""
    policy = {
        'entity_ids': {
            'light.kitchen': True
        }
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is True
    assert compiled('switch.kitchen', ('read',)) is False


def test_entities_entity_ids_entity_id_false():
    """Test entity ID policy."""
    policy = {
        'entity_ids': {
            'light.kitchen': False
        }
    }
    with pytest.raises(vol.Invalid):
        ENTITY_POLICY_SCHEMA(policy)


def test_entities_control_only():
    """Test policy granting control only."""
    policy = {
        'entity_ids': {
            'light.kitchen': {
                'read': True,
            }
        }
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is True
    assert compiled('light.kitchen', ('control',)) is False
    assert compiled('light.kitchen', ('edit',)) is False


def test_entities_read_control():
    """Test policy granting control only."""
    policy = {
        'domains': {
            'light': {
                'read': True,
                'control': True,
            }
        }
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is True
    assert compiled('light.kitchen', ('control',)) is True
    assert compiled('light.kitchen', ('edit',)) is False


def test_entities_all_allow():
    """Test policy allowing all entities."""
    policy = {
        'all': True
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is True
    assert compiled('light.kitchen', ('control',)) is True
    assert compiled('switch.kitchen', ('read',)) is True


def test_entities_all_read():
    """Test policy applying read to all entities."""
    policy = {
        'all': {
            'read': True
        }
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is True
    assert compiled('light.kitchen', ('control',)) is False
    assert compiled('switch.kitchen', ('read',)) is True


def test_entities_all_control():
    """Test entity ID policy applying control to all."""
    policy = {
        'all': {
            'control': True
        }
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', ('read',)) is False
    assert compiled('light.kitchen', ('control',)) is True
    assert compiled('switch.kitchen', ('read',)) is False
    assert compiled('switch.kitchen', ('control',)) is True
