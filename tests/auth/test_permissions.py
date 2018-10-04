"""Tests for the auth permission system."""
from homeassistant.core import State
from homeassistant.auth import permissions


def test_entities_none():
    """Test entity ID policy."""
    policy = None
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is False


def test_entities_empty():
    """Test entity ID policy."""
    policy = {}
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is False


def test_entities_false():
    """Test entity ID policy."""
    policy = False
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is False


def test_entities_true():
    """Test entity ID policy."""
    policy = True
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is True


def test_entities_domains_true():
    """Test entity ID policy."""
    policy = {
        'domains': True
    }
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is True


def test_entities_domains_false():
    """Test entity ID policy."""
    policy = {
        'domains': False
    }
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is False


def test_entities_domains_domain_true():
    """Test entity ID policy."""
    policy = {
        'domains': {
            'light': True
        }
    }
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is True
    assert compiled('switch.kitchen', []) is False


def test_entities_domains_domain_false():
    """Test entity ID policy."""
    policy = {
        'domains': {
            'light': False
        }
    }
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is False
    assert compiled('switch.kitchen', []) is False


def test_entities_entity_ids_true():
    """Test entity ID policy."""
    policy = {
        'entity_ids': True
    }
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is True


def test_entities_entity_ids_false():
    """Test entity ID policy."""
    policy = {
        'entity_ids': False
    }
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is False


def test_entities_entity_ids_entity_id_true():
    """Test entity ID policy."""
    policy = {
        'entity_ids': {
            'light.kitchen': True
        }
    }
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is True
    assert compiled('switch.kitchen', []) is False


def test_entities_precision_order():
    """Test entity ID policy."""
    policy = {
        'entity_ids': False,
        'domains': True,
    }
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is False


def test_entities_entity_ids_entity_id_false():
    """Test entity ID policy."""
    policy = {
        'entity_ids': {
            'light.kitchen': False
        }
    }
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.kitchen', []) is False
    assert compiled('switch.kitchen', []) is False


def test_entities_domain_and_entity_ids():
    """Test entity ID policy whitelist domain, decline entity."""
    policy = {
        'domains': {
            'light': True,
        },
        'entity_ids': {
            'light.kitchen': False
        }
    }
    permissions.ENTITY_POLICY_SCHEMA(policy)
    compiled = permissions._compile_entities(policy)
    assert compiled('light.living_room', []) is True
    assert compiled('light.kitchen', []) is False


def test_policy_perm_filter_entities():
    """Test filtering entitites."""
    states = [
        State('light.kitchen', 'on'),
        State('light.living_room', 'off'),
        State('light.balcony', 'on'),
    ]
    perm = permissions.PolicyPermissions({
        'entities': {
            'entity_ids': {
                'light.kitchen': True,
                'light.balcony': True,
            }
        }
    })
    filtered = perm.filter_entities(states)
    assert len(filtered) == 2
    assert filtered == [states[0], states[2]]


def test_owner_permissions():
    """Test owner permissions access all."""
    assert permissions.OwnerPermissions.check_entity('light.kitchen')
    states = [
        State('light.kitchen', 'on'),
        State('light.living_room', 'off'),
        State('light.balcony', 'on'),
    ]
    assert permissions.OwnerPermissions.filter_entities(states) == states


def test_default_policy_allow_all():
    """Test that the default policy is to allow all entity actions."""
    perm = permissions.PolicyPermissions(permissions.DEFAULT_POLICY)
    assert perm.check_entity('light.kitchen')
    states = [
        State('light.kitchen', 'on'),
        State('light.living_room', 'off'),
        State('light.balcony', 'on'),
    ]
    assert perm.filter_entities(states) == states


def test_merging_permissions_true_rules_all():
    """Test merging policy with two entities."""
    policy1 = {
        'something_else': True,
        'entities': {
            'entity_ids': {
                'light.kitchen': True,
            }
        }
    }
    policy2 = {
        'entities': {
            'entity_ids': True
        }
    }
    assert permissions.merge_policies([policy1, policy2]) == {
        'something_else': True,
        'entities': {
            'entity_ids': True
        }
    }


def test_merging_permissions_multiple_subcategories():
    """Test merging policy with two entities."""
    policy1 = {
        'entities': {
            'entity_ids': {
                'light.kitchen': True,
            }
        }
    }
    policy2 = {
        'entities': {
            'entity_ids': {
                'light.kitchen': False,
                'light.living_room': False,
            }
        }
    }
    assert permissions.merge_policies([policy1, policy2]) == {
        'entities': {
            'entity_ids': {
                'light.kitchen': True,
                'light.living_room': False,
            }
        }
    }
