"""Entity permissions."""
from typing import (  # noqa: F401
    Callable, List, Tuple, Union)

import voluptuous as vol

from .common import CategoryType


ENTITY_DOMAINS = 'domains'
ENTITY_ENTITY_IDS = 'entity_ids'

VALUES_SCHEMA = vol.Any(True, vol.Schema({
    str: True
}))

ENTITY_POLICY_SCHEMA = vol.Any(True, vol.Schema({
    vol.Optional(ENTITY_DOMAINS): VALUES_SCHEMA,
    vol.Optional(ENTITY_ENTITY_IDS): VALUES_SCHEMA,
}))


def compile_entities(policy: CategoryType) \
        -> Callable[[str, Tuple[str]], bool]:
    """Compile policy into a function that tests policy."""
    # None, Empty Dict, False
    if not policy:
        def apply_policy_deny_all(entity_id: str, keys: Tuple[str]) -> bool:
            """Decline all."""
            return False

        return apply_policy_deny_all

    if policy is True:
        def apply_policy_allow_all(entity_id: str, keys: Tuple[str]) -> bool:
            """Approve all."""
            return True

        return apply_policy_allow_all

    assert isinstance(policy, dict)

    domains = policy.get(ENTITY_DOMAINS)
    entity_ids = policy.get(ENTITY_ENTITY_IDS)

    funcs = []  # type: List[Callable[[str, Tuple[str]], Union[None, bool]]]

    # The order of these functions matter. The more precise are at the top.
    # If a function returns None, they cannot handle it.
    # If a function returns a boolean, that's the result to return.

    # Setting entity_ids to a boolean is final decision for permissions
    # So return right away.
    if isinstance(entity_ids, bool):
        def apply_entity_id_policy(entity_id: str, keys: Tuple[str]) -> bool:
            """Test if allowed entity_id."""
            return entity_ids  # type: ignore

        return apply_entity_id_policy

    if entity_ids is not None:
        def allowed_entity_id(entity_id: str, keys: Tuple[str]) \
                -> Union[None, bool]:
            """Test if allowed entity_id."""
            return entity_ids.get(entity_id)  # type: ignore

        funcs.append(allowed_entity_id)

    if isinstance(domains, bool):
        def allowed_domain(entity_id: str, keys: Tuple[str]) \
                -> Union[None, bool]:
            """Test if allowed domain."""
            return domains

        funcs.append(allowed_domain)

    elif domains is not None:
        def allowed_domain(entity_id: str, keys: Tuple[str]) \
                -> Union[None, bool]:
            """Test if allowed domain."""
            domain = entity_id.split(".", 1)[0]
            return domains.get(domain)  # type: ignore

        funcs.append(allowed_domain)

    # Can happen if no valid subcategories specified
    if not funcs:
        def apply_policy_deny_all_2(entity_id: str, keys: Tuple[str]) -> bool:
            """Decline all."""
            return False

        return apply_policy_deny_all_2

    if len(funcs) == 1:
        func = funcs[0]

        def apply_policy_func(entity_id: str, keys: Tuple[str]) -> bool:
            """Apply a single policy function."""
            return func(entity_id, keys) is True

        return apply_policy_func

    def apply_policy_funcs(entity_id: str, keys: Tuple[str]) -> bool:
        """Apply several policy functions."""
        for func in funcs:
            result = func(entity_id, keys)
            if result is not None:
                return result
        return False

    return apply_policy_funcs
