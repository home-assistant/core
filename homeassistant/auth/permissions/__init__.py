"""Permissions for Home Assistant."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import voluptuous as vol

from .const import CAT_ENTITIES
from .entities import ENTITY_POLICY_SCHEMA, compile_entities
from .models import PermissionLookup
from .types import PolicyType
from .util import test_all

POLICY_SCHEMA = vol.Schema({vol.Optional(CAT_ENTITIES): ENTITY_POLICY_SCHEMA})

__all__ = [
    "POLICY_SCHEMA",
    "PermissionLookup",
    "PolicyType",
    "AbstractPermissions",
    "PolicyPermissions",
    "OwnerPermissions",
]


class AbstractPermissions:
    """Default permissions class."""

    _cached_entity_func: Callable[[str, str], bool] | None = None

    def _entity_func(self) -> Callable[[str, str], bool]:
        """Return a function that can test entity access."""
        raise NotImplementedError

    def access_all_entities(self, key: str) -> bool:
        """Check if we have a certain access to all entities."""
        raise NotImplementedError

    def check_entity(self, entity_id: str, key: str) -> bool:
        """Check if we can access entity."""
        if (entity_func := self._cached_entity_func) is None:
            entity_func = self._cached_entity_func = self._entity_func()

        return entity_func(entity_id, key)


class PolicyPermissions(AbstractPermissions):
    """Handle permissions."""

    def __init__(
        self, policies: list[PolicyType], perm_lookup: PermissionLookup
    ) -> None:
        """Initialize the permission class."""
        self._policies = policies
        self._perm_lookup = perm_lookup

    def access_all_entities(self, key: str) -> bool:
        """Check if we have a certain access to all entities."""
        return any(test_all(policy.get(CAT_ENTITIES), key) for policy in self._policies)

    def _entity_func(self) -> Callable[[str, str], bool]:
        """Return a function that can test entity access."""
        return compile_entities(
            [policy.get(CAT_ENTITIES) for policy in self._policies], self._perm_lookup
        )

    def __eq__(self, other: Any) -> bool:
        """Equals check."""
        return (
            isinstance(other, PolicyPermissions) and other._policies == self._policies
        )


class _OwnerPermissions(AbstractPermissions):
    """Owner permissions."""

    def access_all_entities(self, key: str) -> bool:
        """Check if we have a certain access to all entities."""
        return True

    def _entity_func(self) -> Callable[[str, str], bool]:
        """Return a function that can test entity access."""
        return lambda entity_id, key: True


OwnerPermissions = _OwnerPermissions()
