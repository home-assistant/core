"""
Provides functionality to interact with fans.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/fan/
"""
import logging
import os

import voluptuous as vol

from homeassistant.components import (
    insteon_hub,
    group,
)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    STATE_ON,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_LOW,
    STATE_MED,
    STATE_HIGH,
    SERVICE_SET_VALUE,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv

DOMAIN = "fan"
SCAN_INTERVAL = 30

GROUP_NAME_ALL_FANS = 'all fans'
ENTITY_ID_ALL_FANS = group.ENTITY_ID_FORMAT.format('all_fans')

ENTITY_ID_FORMAT = DOMAIN + ".{}"

# String representing the speed setting for the fan
ATTR_SPEED = "value"

# String representing a profile (built-in ones or external defined).
ATTR_PROFILE = "profile"

FAN_PROFILES_FILE = "fan_profiles.csv"

# Maps discovered services to their platforms.
DISCOVERY_PLATFORMS = {
    insteon_hub.DISCOVERY[DOMAIN]: 'insteon_hub',
}

PROP_TO_ATTR = {
    'value': ATTR_SPEED,
}


# Service call validation schemas
def is_valid_speed(val):
    """Check if the value is valid."""
    if (isinstance(val, str) and
            val in [
                STATE_OFF,
                STATE_LOW,
                STATE_MED,
                STATE_HIGH]):
        return val
    return vol.Invalid('Not a valid speed setting')

FAN_SET_SPEED_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    ATTR_SPEED: is_valid_speed
})

PROFILE_SCHEMA = vol.Schema(
    vol.ExactSequence((str, cv.small_float, cv.small_float, cv.byte))
)

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """Return if the lights are on based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_FANS
    return hass.states.is_state(entity_id, STATE_ON)


# pylint: disable=too-many-arguments
def set_value(hass, entity_id=None, level=None):
    """Set the fan speed."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_SPEED, level),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_SET_VALUE, data)


# pylint: disable=too-many-branches, too-many-locals, too-many-statements
def setup(hass, config):
    """Expose light control via statemachine and services."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DISCOVERY_PLATFORMS,
        GROUP_NAME_ALL_FANS)
    component.setup(config)

    def handle_fan_service(service):
        """Hande a turn light on or off service call."""
        # Get the validated data
        params = service.data.copy()

        # Convert the entity ids to valid light ids
        target_fans = component.extract_from_service(service)
        params.pop(ATTR_ENTITY_ID, None)

        service_fun = None
        if service.service == SERVICE_SET_VALUE:
            service_fun = 'set_value'

        if service_fun:
            for fan in target_fans:
                getattr(fan, service_fun)(**params)

            for fan in target_fans:
                if fan.should_poll:
                    fan.update_ha_state(True)
            return

        for fan in target_fans:
            if fan.should_poll:
                fan.update_ha_state(True)

    # Listen for fan on and light off service calls.
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, SERVICE_SET_VALUE, handle_fan_service,
                           descriptions.get(SERVICE_SET_VALUE),
                           schema=FAN_SET_SPEED_SCHEMA)

    return True
