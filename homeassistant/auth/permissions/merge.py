"""Merging of policies."""
from __future__ import annotations

from typing import cast

from .types import CategoryType, PolicyType


def merge_policies(policies: list[PolicyType]) -> PolicyType:
    """Merge policies."""
    new_policy: dict[str, CategoryType] = {}
    seen: set[str] = set()
    for policy in policies:
        for category in policy:
            if category in seen:
                continue
            seen.add(category)
            new_policy[category] = _merge_policies(
                [policy.get(category) for policy in policies]
            )
    cast(PolicyType, new_policy)
    return new_policy


from typing import Dict, Union, List

CategoryType = Union[bool, Dict[str, "CategoryType"]]


def _merge_policies(sources: List[CategoryType]) -> CategoryType:
    """Merge a policy."""
    # When merging policies, the most permissive wins.
    # This means we order it like this:
    # True > Dict > None
    #
    # True: allow everything
    # Dict: specify more granular permissions
    # None: no opinion
    #
    # If there are multiple sources with a dict as policy, we recursively
    # merge each key in the source.

    def merge_dicts(dicts: List[Dict[str, CategoryType]]) -> Dict[str, CategoryType]:
        merged_dict: Dict[str, CategoryType] = {}
        seen: set[str] = set()
        for dictionary in dicts:
            for key, value in dictionary.items():
                if key not in seen:
                    seen.add(key)
                    if key in merged_dict and isinstance(value, dict):
                        # Recursively merge sub-dictionaries
                        merged_dict[key] = merge_dicts(
                            [d.get(key, {}) for d in dicts if isinstance(d, dict)]
                        )
                    else:
                        merged_dict[key] = value
        return merged_dict

    result: CategoryType = None
    for source in sources:
        if source is True:
            return True
        elif isinstance(source, dict):
            if result is None:
                result = {}
            if isinstance(result, dict):
                result = merge_dicts([result, source])
    return result
