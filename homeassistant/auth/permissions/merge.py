"""Merging of policies."""
from typing import (  # noqa: F401
    cast, Dict, List, Set)

from .common import PolicyType, CategoryType


def merge_policies(policies: List[PolicyType]) -> PolicyType:
    """Merge policies."""
    new_policy = {}  # type: Dict[str, CategoryType]
    seen = set()  # type: Set[str]
    for policy in policies:
        for category in policy:
            if category in seen:
                continue
            seen.add(category)
            new_policy[category] = _merge_policies([
                policy.get(category) for policy in policies])
    cast(PolicyType, new_policy)
    return new_policy


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

    policy = None  # type: CategoryType
    seen = set()  # type: Set[str]
    for source in sources:
        if source is None:
            continue

        # A source that's True will always win. Shortcut return.
        if source is True:
            return True

        assert isinstance(source, dict)

        if policy is None:
            policy = cast(CategoryType, {})

        assert isinstance(policy, dict)

        for key in source:
            if key in seen:
                continue
            seen.add(key)

            key_sources = []
            for src in sources:
                if isinstance(src, dict):
                    key_sources.append(src.get(key))

            policy[key] = _merge_policies(key_sources)

    return policy
