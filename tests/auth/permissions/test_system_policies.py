"""Test system policies."""
from homeassistant.auth.permissions import (
    POLICY_SCHEMA,
    PolicyPermissions,
    system_policies,
)


def test_admin_policy():
    """Test admin policy works."""
    # Make sure it's valid
    POLICY_SCHEMA(system_policies.ADMIN_POLICY)

    perms = PolicyPermissions(system_policies.ADMIN_POLICY, None)
    assert perms.check_entity("light.kitchen", "read")
    assert perms.check_entity("light.kitchen", "control")
    assert perms.check_entity("light.kitchen", "edit")


def test_user_policy():
    """Test user policy works."""
    # Make sure it's valid
    POLICY_SCHEMA(system_policies.USER_POLICY)

    perms = PolicyPermissions(system_policies.USER_POLICY, None)
    assert perms.check_entity("light.kitchen", "read")
    assert perms.check_entity("light.kitchen", "control")
    assert perms.check_entity("light.kitchen", "edit")


def test_read_only_policy():
    """Test read only policy works."""
    # Make sure it's valid
    POLICY_SCHEMA(system_policies.READ_ONLY_POLICY)

    perms = PolicyPermissions(system_policies.READ_ONLY_POLICY, None)
    assert perms.check_entity("light.kitchen", "read")
    assert not perms.check_entity("light.kitchen", "control")
    assert not perms.check_entity("light.kitchen", "edit")
