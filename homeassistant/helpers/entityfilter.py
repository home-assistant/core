"""Helper class to implement include/exclude of entities and domains."""

from homeassistant.const import (
    CONF_ENTITIES, CONF_DOMAINS)
from homeassistant.core import split_entity_id


class EntityFilter():
    """Class that implements an include/exclude filter for entities/domains."""

    def __init__(self, include_dict, exclude_dict):
        """Set up the filter."""
        self.include_e = include_dict.get(CONF_ENTITIES, [])
        self.include_d = include_dict.get(CONF_DOMAINS, [])
        self.exclude_e = exclude_dict.get(CONF_ENTITIES, [])
        self.exclude_d = exclude_dict.get(CONF_DOMAINS, [])

        if self.exclude_e + self.exclude_d == []:
            self.have_exclude = False
        else:
            self.have_exclude = True

        if self.include_e + self.include_d == []:
            self.have_include = False
        else:
            self.have_include = True

    def check_entity(self, entity_id):
        """Check if a given entity_id should be filtered."""
        domain = split_entity_id(entity_id)[0]

        # Case 1 - no includes or excludes - pass all entities
        if not self.have_include and not self.have_exclude:
            return True

        # Case 2 - includes, no excludes - only include specified entities
        if self.have_include and not self.have_exclude:
            return bool(entity_id in self.include_e or
                        domain in self.include_d)

        # Case 3 - excludes, no includes - only exclude specified entities
        if not self.have_include and self.have_exclude:
            if entity_id in self.exclude_e or domain in self.exclude_d:
                return False
            else:
                return True

        # Case 4 - both includes and excludes specified
        # Case 4a - include domain specified
        #  - if domain is included, and entity not excluded, pass
        #  - if domain is not included, and entity not included, fail
        # note: if both include and exclude domains specified,
        #   the exclude domains are ignored
        if self.include_d:
            if domain in self.include_d:
                return bool(entity_id not in self.exclude_e)
            else:
                return bool(entity_id in self.include_e)

        # Case 4b - exclude domain specified
        #  - if domain is excluded, and entity not included, fail
        #  - if domain is not excluded, and entity not excluded, pass
        if self.exclude_d:
            if domain in self.exclude_d:
                return bool(entity_id in self.include_e)
            else:
                return bool(entity_id not in self.exclude_e)

        # Case 4c - neither include or exclude domain specified
        #  - Only pass if entity is included.  Ignore entity excludes.
        if entity_id in self.include_e:
            return True

        return False
