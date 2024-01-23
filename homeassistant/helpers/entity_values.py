"""A class to hold entity values."""
from __future__ import annotations

from collections import OrderedDict
import fnmatch
from functools import lru_cache
import re
from typing import Any

from homeassistant.core import split_entity_id

_MAX_EXPECTED_ENTITIES = 16384


class EntityValues:
    """Class to store entity id based values.

    This class is expected to only be used infrequently
    as it caches all entity ids up to _MAX_EXPECTED_ENTITIES.

    The cache includes `self` so it is important to
    only use this in places where usage of `EntityValues` is immortal.
    """

    def __init__(
        self,
        exact: dict[str, dict[str, str]] | None = None,
        domain: dict[str, dict[str, str]] | None = None,
        glob: dict[str, dict[str, str]] | None = None,
    ) -> None:
        """Initialize an EntityConfigDict."""
        self._exact = exact
        self._domain = domain

        if glob is None:
            compiled: dict[re.Pattern[str], Any] | None = None
        else:
            compiled = OrderedDict()
            for key, value in glob.items():
                compiled[re.compile(fnmatch.translate(key))] = value

        self._glob = compiled

    @lru_cache(maxsize=_MAX_EXPECTED_ENTITIES)
    def get(self, entity_id: str) -> dict[str, str]:
        """Get config for an entity id."""
        domain, _ = split_entity_id(entity_id)
        result: dict[str, str] = {}

        if self._domain is not None and domain in self._domain:
            result.update(self._domain[domain])

        if self._glob is not None:
            for pattern, values in self._glob.items():
                if pattern.match(entity_id):
                    result.update(values)

        if self._exact is not None and entity_id in self._exact:
            result.update(self._exact[entity_id])

        return result
