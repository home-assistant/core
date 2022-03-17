"""Helpers to deal with permissions."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Optional, cast

from .const import SUBCAT_ALL
from .models import PermissionLookup
from .types import CategoryType, SubCategoryDict, ValueType

LookupFunc = Callable[[PermissionLookup, SubCategoryDict, str], Optional[ValueType]]
SubCatLookupType = dict[str, LookupFunc]


def lookup_all(
    perm_lookup: PermissionLookup, lookup_dict: SubCategoryDict, object_id: str
) -> ValueType:
    """Look up permission for all."""
    # In case of ALL category, lookup_dict IS the schema.
    return cast(ValueType, lookup_dict)


def _apply_policy_deny_all(entity_id: str, key: str) -> bool:
    """Decline all."""
    return False


def _apply_policy_allow_all(entity_id: str, key: str) -> bool:
    """Approve all."""
    return True


def compile_policy(
    policy: CategoryType, subcategories: SubCatLookupType, perm_lookup: PermissionLookup
) -> Callable[[str, str], bool]:
    """Compile policy into a function that tests policy.

    Subcategories are mapping key -> lookup function, ordered by highest
    priority first.
    """
    # None, False, empty dict
    if not policy:
        return _apply_policy_deny_all

    if policy is True:
        return _apply_policy_allow_all

    assert isinstance(policy, dict)

    funcs: list[Callable[[str, str], bool | None]] = []

    for key, lookup_func in subcategories.items():
        lookup_value = policy.get(key)

        # If any lookup value is `True`, it will always be positive
        if lookup_value is True:
            funcs.append(_apply_policy_allow_all)
        elif lookup_value is False:
            funcs.append(_apply_policy_deny_all)
        elif lookup_value is not None:
            funcs.append(_gen_dict_test_func(perm_lookup, lookup_func, lookup_value))

    if len(funcs) == 1:
        func = funcs[0]

        if func is _apply_policy_allow_all or func is _apply_policy_deny_all:
            return cast("Callable[[str, str], bool]", func)

        @wraps(func)
        def apply_policy_func(object_id: str, key: str) -> bool:
            """Apply a single policy function."""
            return func(object_id, key) is True

        return apply_policy_func

    def apply_policy_funcs(object_id: str, key: str) -> bool:
        """Apply several policy functions."""
        for func in funcs:
            if (result := func(object_id, key)) is not None:
                return result
        return False

    return apply_policy_funcs


def compile_merged_policy(
    policies: list[CategoryType],
    subcategories: SubCatLookupType,
    perm_lookup: PermissionLookup,
) -> Callable[[str, str], bool]:
    """Compile an additive set of policies into a function that tests policy.

    Subcategories are mapping key -> lookup function, ordered by highest
    priority first.
    """

    raw_policy_funcs = [
        compile_policy(policy, subcategories, perm_lookup) for policy in policies
    ]
    policy_funcs = [f for f in raw_policy_funcs if f is not _apply_policy_deny_all]

    if not policy_funcs:
        return _apply_policy_deny_all

    if any(policy_func is _apply_policy_allow_all for policy_func in policy_funcs):
        return _apply_policy_allow_all

    if len(policy_funcs) == 1:
        return policy_funcs[0]

    return lambda object_id, key: any(
        policy_func(object_id, key) for policy_func in policy_funcs
    )


def _gen_dict_test_func(
    perm_lookup: PermissionLookup, lookup_func: LookupFunc, lookup_dict: SubCategoryDict
) -> Callable[[str, str], bool | None]:
    """Generate a lookup function."""

    def test_value(object_id: str, key: str) -> bool | None:
        """Test if permission is allowed based on the keys."""
        schema: ValueType = lookup_func(perm_lookup, lookup_dict, object_id)

        if schema is None or isinstance(schema, bool):
            return schema

        assert isinstance(schema, dict)

        return schema.get(key)

    return test_value


def test_all(policy: CategoryType, key: str) -> bool:
    """Test if a policy has an ALL access for a specific key."""
    if not isinstance(policy, dict):
        return bool(policy)

    all_policy = policy.get(SUBCAT_ALL)

    if not isinstance(all_policy, dict):
        return bool(all_policy)

    return all_policy.get(key, False) is True
