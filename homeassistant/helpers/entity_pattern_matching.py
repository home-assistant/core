"""A Class to handle matching entity_ids through patterns."""
import fnmatch
import re

from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components.zwave.const import EVENT_NETWORK_READY


class EntityPatternMatching(object):
    """Class to generate patterns and match entity_ids."""

    def __init__(self, hass, action, entity_list):
        """Initialize and EntityPatternMatching (EPM) object."""
        self.hass = hass
        self.action = action
        self.entity_list = entity_list
        self.pattern = set()
        self.entity_ids = set()
        self.entity_ids_matched = set()
        self.start_matching()

    def start_matching(self):
        """Start the matching process."""
        self.filter_entity_ids()
        self.report_entity_ids()
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self.report_matched_entity_ids)
        self.hass.bus.async_listen_once(
            EVENT_NETWORK_READY, self.report_matched_entity_ids)

    def filter_entity_ids(self):
        """Filter patterns from the entity_list."""
        for entity in self.entity_list:
            if entity.find('*') != -1 or entity.find('?') != -1 or \
               entity.find('[') != -1:
                self.pattern.add(re.compile(fnmatch.translate(entity)))
            else:
                self.entity_ids.add(entity)

    def match_entity_ids(self):
        """Match entity_ids through saved patterns."""
        all_ids = self.hass.states.async_entity_ids()
        for entity in self.entity_ids_matched:
            if entity in all_ids:
                all_ids.remove(entity)

        for pattern in self.pattern:
            for entity in all_ids[:]:
                if pattern.match(entity):
                    all_ids.remove(entity)
                    self.entity_ids.add(entity)
                    self.entity_ids_matched.add(entity)

    def report_entity_ids(self):
        """Report all entity_ids after filtering."""
        self.hass.async_run_job(self.action, self.entity_ids)
        self.entity_ids.clear()

    @callback
    def report_matched_entity_ids(self, event):
        """Report all matched entity_ids."""
        self.match_entity_ids()
        self.hass.async_run_job(self.action, self.entity_ids)
        self.entity_ids.clear()
