"""Tests for permissions merging."""
from homeassistant.auth.permissions.merge import merge_policies


def test_merging_permissions_true_rules_dict():
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
    assert merge_policies([policy1, policy2]) == {
        'something_else': True,
        'entities': {
            'entity_ids': True
        }
    }


def test_merging_permissions_multiple_subcategories():
    """Test merging policy with two entities."""
    policy1 = {
        'entities': None
    }
    policy2 = {
        'entities': {
            'entity_ids': True,
        }
    }
    policy3 = {
        'entities': True
    }
    assert merge_policies([policy1, policy2]) == policy2
    assert merge_policies([policy1, policy3]) == policy3

    assert merge_policies([policy2, policy3]) == policy3
