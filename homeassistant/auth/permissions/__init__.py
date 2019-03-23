"""Permissions for Home Assistant."""
import logging
from typing import (  # noqa: F401
    cast, Any, Callable, Dict, List, Mapping, Set, Tuple, Union,
    TYPE_CHECKING)

import voluptuous as vol

from .const import CAT_ENTITIES
from .models import PermissionLookup
from .types import PolicyType
from .entities import ENTITY_POLICY_SCHEMA, compile_entities
from .merge import merge_policies  # noqa


POLICY_SCHEMA = vol.Schema({
    vol.Optional(CAT_ENTITIES): ENTITY_POLICY_SCHEMA
})

_LOGGER = logging.getLogger(__name__)


class AbstractPermissions:
    """Default permissions class."""

    _cached_entity_func = None

    def _entity_func(self) -> Callable[[str, str], bool]:
        """Return a function that can test entity access."""
        raise NotImplementedError

    def check_entity(self, entity_id: str, key: str) -> bool:
        """Check if we can access entity."""
        entity_func = self._cached_entity_func

        if entity_func is None:
            entity_func = self._cached_entity_func = self._entity_func()

        return entity_func(entity_id, key)


class PolicyPermissions(AbstractPermissions):
    """Handle permissions."""

    def __init__(self, policy: PolicyType,
                 perm_lookup: PermissionLookup) -> None:
        """Initialize the permission class."""
        self._policy = policy
        self._perm_lookup = perm_lookup

    def _entity_func(self) -> Callable[[str, str], bool]:
        """Return a function that can test entity access."""
        return compile_entities(self._policy.get(CAT_ENTITIES),
                                self._perm_lookup)

    def __eq__(self, other: Any) -> bool:
        """Equals check."""
        # pylint: disable=protected-access
        return (isinstance(other, PolicyPermissions) and
                other._policy == self._policy)


class _OwnerPermissions(AbstractPermissions):
    """Owner permissions."""

    # pylint: disable=no-self-use

    def _entity_func(self) -> Callable[[str, str], bool]:
        """Return a function that can test entity access."""
        return lambda entity_id, key: True


OwnerPermissions = _OwnerPermissions()  # pylint: disable=invalid-name
