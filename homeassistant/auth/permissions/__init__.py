"""Permissions for Home Assistant."""
import logging
from typing import (  # noqa: F401
    cast, Any, Callable, Dict, List, Mapping, Set, Tuple, Union)

import voluptuous as vol

from homeassistant.core import State

from .const import CAT_ENTITIES
from .types import CategoryType, PolicyType
from .entities import ENTITY_POLICY_SCHEMA, compile_entities
from .merge import merge_policies  # noqa

POLICY_SCHEMA = vol.Schema({
    vol.Optional(CAT_ENTITIES): ENTITY_POLICY_SCHEMA
})

_LOGGER = logging.getLogger(__name__)


class AbstractPermissions:
    """Default permissions class."""

    def entity_func(self) -> Callable[[str, Tuple[str, ...]], bool]:
        """Return a function that can test entity access."""
        raise NotImplementedError

    def check_entity(self, entity_id: str, key: str) -> bool:
        """Test if we can access entity."""
        return self.entity_func()(entity_id, (key,))

    def filter_states(self, states: List[State]) -> List[State]:
        """Filter a list of states for what the user is allowed to see."""
        func = self.entity_func()
        keys = ('read',)
        return [entity for entity in states if func(entity.entity_id, keys)]


class PolicyPermissions(AbstractPermissions):
    """Handle permissions."""

    def __init__(self, policy: PolicyType) -> None:
        """Initialize the permission class."""
        self._policy = policy
        self._compiled = {}  # type: Dict[str, Callable[..., bool]]

    def entity_func(self) -> Callable[[str, Tuple[str, ...]], bool]:
        """Return a function that can test entity access."""
        return self._policy_func(CAT_ENTITIES, compile_entities)

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

    def entity_func(self) -> Callable[[str, Tuple[str, ...]], bool]:
        """Return a function that can test entity access."""
        return lambda entity_id, keys: True


OwnerPermissions = _OwnerPermissions()  # pylint: disable=invalid-name
