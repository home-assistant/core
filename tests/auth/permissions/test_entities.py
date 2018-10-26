"""Tests for entity permissions."""
import pytest
import voluptuous as vol

from homeassistant.auth.permissions.entities import (
  compile_entities, ENTITY_POLICY_SCHEMA)


def test_entities_none():
    """Test entity ID policy."""
    policy = None
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', []) is False


def test_entities_empty():
    """Test entity ID policy."""
    policy = {}
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', []) is False


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
    assert compiled('light.kitchen', []) is True


def test_entities_domains_true():
    """Test entity ID policy."""
    policy = {
        'domains': True
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', []) is True


def test_entities_domains_domain_true():
    """Test entity ID policy."""
    policy = {
        'domains': {
            'light': True
        }
    }
    ENTITY_POLICY_SCHEMA(policy)
    compiled = compile_entities(policy)
    assert compiled('light.kitchen', []) is True
    assert compiled('switch.kitchen', []) is False


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
    assert compiled('light.kitchen', []) is True


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
    assert compiled('light.kitchen', []) is True
    assert compiled('switch.kitchen', []) is False


def test_entities_entity_ids_entity_id_false():
    """Test entity ID policy."""
    policy = {
        'entity_ids': {
            'light.kitchen': False
        }
    }
    with pytest.raises(vol.Invalid):
        ENTITY_POLICY_SCHEMA(policy)
