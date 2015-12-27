"""
homeassistant.components.option
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with options, where one option out of an option group can be selected.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/option/
"""
import logging

import os

from homeassistant.components import cec
from homeassistant.config import load_yaml_config_file
from homeassistant.const import SERVICE_SET_OPTION, ATTR_ENTITY_ID
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'option'
SCAN_INTERVAL = 30

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# strings that represents the desired option
ATTR_OPTION = "option"
ATTR_OPTIONS = "options"

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PLATFORMS = {
    cec.DISCOVER_OPTION: 'cec',
}

DEVICE_NAME = 'Active HDMI device'


def set_option(hass, option, entity_id=None):
    """ Will select the specified option. """
    data = {ATTR_OPTION: option}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_OPTION, data)


def setup(hass, config):
    """ Setup options. """
    component = EntityComponent(_LOGGER, DOMAIN, hass,
                                SCAN_INTERVAL, DISCOVERY_PLATFORMS)
    component.setup(config)

    def option_service(service):
        """ Handles calls to the services. """
        # Get and validate data
        dat = service.data

        # Convert the entity ids to valid light ids
        target_options = component.extract_from_service(service)

        option = service.data.get(ATTR_OPTION)

        if option is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_OPTION, ATTR_OPTION)

        else:
            for target_option in target_options:
                target_option.switch(option)

            for target_option in target_options:
                if target_option.should_poll:
                    target_option.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    print("descriptions", descriptions)

    hass.services.register(
        DOMAIN, SERVICE_SET_OPTION, option_service,
        descriptions.get(SERVICE_SET_OPTION))

    return True


class OptionDevice(Entity):
    """ Represents an option within Home Assistant. """

    @property
    def name(self):
        """ Returns the name of the entity. """
        return DEVICE_NAME

    @property
    def state(self):
        """ Returns the state of the entity. """
        return self.option

    @property
    def option(self):
        """ Returns the active option of the entity. """
        return None

    @property
    def options(self):
        """ Returns the list of available options for this entity. """
        return []

    def switch(self, option, **kwargs):
        """ Select the option 'option' for this entity. """
        pass

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        data = {
            ATTR_OPTION: self.option,
            ATTR_OPTIONS: self.options,
        }

        return data
