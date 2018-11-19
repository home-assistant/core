"""Permissions for Home Assistant."""
import logging
from typing import (  # noqa: F401
    cast, Any, Callable, Dict, List, Mapping, Set, Tuple, Union)

import voluptuous as vol

from homeassistant.core import State

from .common import CategoryType, PolicyType
from .entities import ENTITY_POLICY_SCHEMA, compile_entities
from .merge import merge_policies  # noqa


# Default policy if group has no policy applied.
DEFAULT_POLICY = {
    "entities": True
}  # type: PolicyType

CAT_ENTITIES = 'entities'

POLICY_SCHEMA = vol.Schema({
    vol.Optional(CAT_ENTITIES): ENTITY_POLICY_SCHEMA
})

_LOGGER = logging.getLogger(__name__)


class AbstractPermissions:
    """Default permissions class."""

    def check_entity(self, entity_id: str, key: str) -> bool:
        """Test if we can access entity."""
        raise NotImplementedError

    def filter_states(self, states: List[State]) -> List[State]:
        """Filter a list of states for what the user is allowed to see."""
        raise NotImplementedError


class PolicyPermissions(AbstractPermissions):
    """Handle permissions."""

    def __init__(self, policy: PolicyType) -> None:
        """Initialize the permission class."""
        self._policy = policy
        self._compiled = {}  # type: Dict[str, Callable[..., bool]]

    def check_entity(self, entity_id: str, key: str) -> bool:
        """Test if we can access entity."""
        func = self._policy_func(CAT_ENTITIES, compile_entities)
        return func(entity_id, (key,))

    def filter_states(self, states: List[State]) -> List[State]:
        """Filter a list of states for what the user is allowed to see."""
        func = self._policy_func(CAT_ENTITIES, compile_entities)
        keys = ('read',)
        return [entity for entity in states if func(entity.entity_id, keys)]

    def _policy_func(self, category: str,
                     compile_func: Callable[[CategoryType], Callable]) \
            -> Callable[..., bool]:
        """Get a policy function."""
        func = self._compiled.get(category)

        if func:
            return func

        func = self._compiled[category] = compile_func(
            self._policy.get(category))

        _LOGGER.debug("Compiled %s func: %s", category, func)

        return func

    def __eq__(self, other: Any) -> bool:
        """Equals check."""
        # pylint: disable=protected-access
        return (isinstance(other, PolicyPermissions) and
                other._policy == self._policy)


class _OwnerPermissions(AbstractPermissions):
    """Owner permissions."""

    # pylint: disable=no-self-use

    def check_entity(self, entity_id: str, key: str) -> bool:
        """Test if we can access entity."""
        return True

    def filter_states(self, states: List[State]) -> List[State]:
        """Filter a list of states for what the user is allowed to see."""
        return states


OwnerPermissions = _OwnerPermissions()  # pylint: disable=invalid-name
