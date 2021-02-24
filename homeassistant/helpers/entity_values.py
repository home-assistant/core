"""A class to hold entity values."""
from collections import OrderedDict
import fnmatch
import re
from typing import Any, Dict, Optional, Pattern

from homeassistant.core import split_entity_id

# mypy: disallow-any-generics


class EntityValues:
    """Class to store entity id based values."""

    def __init__(
        self,
        exact: Optional[Dict[str, Dict[str, str]]] = None,
        domain: Optional[Dict[str, Dict[str, str]]] = None,
        glob: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> None:
        """Initialize an EntityConfigDict."""
        self._cache: Dict[str, Dict[str, str]] = {}
        self._exact = exact
        self._domain = domain

        if glob is None:
            compiled: Optional[Dict[Pattern[str], Any]] = None
        else:
            compiled = OrderedDict()
            for key, value in glob.items():
                compiled[re.compile(fnmatch.translate(key))] = value

        self._glob = compiled

    def get(self, entity_id: str) -> Dict[str, str]:
        """Get config for an entity id."""
        if entity_id in self._cache:
            return self._cache[entity_id]

        domain, _ = split_entity_id(entity_id)
        result = self._cache[entity_id] = {}

        if self._domain is not None and domain in self._domain:
            result.update(self._domain[domain])

        if self._glob is not None:
            for pattern, values in self._glob.items():
                if pattern.match(entity_id):
                    result.update(values)

        if self._exact is not None and entity_id in self._exact:
            result.update(self._exact[entity_id])

        return result
