"""Tests for the auth permission system."""
from homeassistant.core import State
from homeassistant.auth import permissions


def test_policy_perm_filter_states():
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
    filtered = perm.filter_states(states)
    assert len(filtered) == 2
    assert filtered == [states[0], states[2]]


def test_owner_permissions():
    """Test owner permissions access all."""
    assert permissions.OwnerPermissions.check_entity('light.kitchen', 'write')
    states = [
        State('light.kitchen', 'on'),
        State('light.living_room', 'off'),
        State('light.balcony', 'on'),
    ]
    assert permissions.OwnerPermissions.filter_states(states) == states


def test_default_policy_allow_all():
    """Test that the default policy is to allow all entity actions."""
    perm = permissions.PolicyPermissions(permissions.DEFAULT_POLICY)
    assert perm.check_entity('light.kitchen', 'read')
    states = [
        State('light.kitchen', 'on'),
        State('light.living_room', 'off'),
        State('light.balcony', 'on'),
    ]
    assert perm.filter_states(states) == states
