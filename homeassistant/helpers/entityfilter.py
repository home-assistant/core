"""Helper class to implement include/exclude of entities and domains."""

from homeassistant.core import split_entity_id


class EntityFilter():
    """Class that implements an include/exclude filter for entities/domains."""

    def __init__(self, include_domains, include_entities,
                 exclude_domains, exclude_entities):
        """Set up the filter."""
        self.include_d = set(include_domains)
        self.include_e = set(include_entities)
        self.exclude_d = set(exclude_domains)
        self.exclude_e = set(exclude_entities)

        self.have_exclude = bool(self.exclude_e or self.exclude_d)
        self.have_include = bool(self.include_e or self.include_d)

    def check_entity(self, entity_id):
        """Check if a given entity_id should be filtered."""
        domain = split_entity_id(entity_id)[0]

        # Case 1 - no includes or excludes - pass all entities
        if not self.have_include and not self.have_exclude:
            return True

        # Case 2 - includes, no excludes - only include specified entities
        if self.have_include and not self.have_exclude:
            return entity_id in self.include_e or \
                        domain in self.include_d

        # Case 3 - excludes, no includes - only exclude specified entities
        if not self.have_include and self.have_exclude:
            return entity_id not in self.exclude_e and \
                        domain not in self.exclude_d

        # Case 4 - both includes and excludes specified
        # Case 4a - include domain specified
        #  - if domain is included, and entity not excluded, pass
        #  - if domain is not included, and entity not included, fail
        # note: if both include and exclude domains specified,
        #   the exclude domains are ignored
        if self.include_d:
            if domain in self.include_d:
                return entity_id not in self.exclude_e
            else:
                return entity_id in self.include_e

        # Case 4b - exclude domain specified
        #  - if domain is excluded, and entity not included, fail
        #  - if domain is not excluded, and entity not excluded, pass
        if self.exclude_d:
            if domain in self.exclude_d:
                return entity_id in self.include_e
            else:
                return entity_id not in self.exclude_e

        # Case 4c - neither include or exclude domain specified
        #  - Only pass if entity is included.  Ignore entity excludes.
        if entity_id in self.include_e:
            return True

        return False
