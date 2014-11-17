"""
homeassistant.components.scheduler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
import logging
from datetime import datetime, timedelta
import json
from pprint import pprint
import importlib

from homeassistant.components import switch, sun
from homeassistant.loader import get_component

# The domain of your component. Should be equal to the name of your component
DOMAIN = 'scheduler'

# List of component names (string) your component depends upon
# If you are setting up a group but not using a group for anything,
# don't depend on group
DEPENDENCIES = ['sun']

_LOGGER = logging.getLogger(__name__)

_SCHEDULE_FILE = 'schedule.json'
_RULE_TYPE_CACHE = {}


# pylint: disable=unused-argument
def setup(hass, config):
    """ Register services or listen for events that your component needs. """

    def setup_schedule(description):

        for rule in description['rules']:
            rule_init = get_component('scheduler.{}'.format(rule['type']))

            if rule_init is None:
                _LOGGER.error('Error loading schedule rule %s', rule['type'])
                return False

        return True

    with open(hass.get_config_path(_SCHEDULE_FILE)) as schedule_file:
        schedule_descriptions = json.load(schedule_file)

    for schedule_description in schedule_descriptions:
        if not setup_schedule(schedule_description):
            return False

    return True
