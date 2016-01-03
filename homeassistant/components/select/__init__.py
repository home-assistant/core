"""
homeassistant.components.select
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component that allows to select one possible option out of a selection of options.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/select/
"""
import logging

import os

from homeassistant.config import load_yaml_config_file
from homeassistant.const import SERVICE_SET_OPTION, ATTR_ENTITY_ID
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'select'
SCAN_INTERVAL = 30

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# string that represents the desired option
ATTR_OPTION = "option"

# string that represents all available options
ATTR_OPTIONS = "options"

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PLATFORMS = {
}


def set_option(hass, option, entity_id=None):
    """ Will select the specified option. """
    data = {ATTR_OPTION: option}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_OPTION, data)


def setup(hass, config):
    """ Setup selects. """
    component = EntityComponent(_LOGGER, DOMAIN, hass,
                                SCAN_INTERVAL, DISCOVERY_PLATFORMS)
    component.setup(config)

    def option_service(service):
        """ Handles calls to the services. """
        # Get and validate data
        dat = service.data

        # Convert the entity ids to valid select ids
        target_selects = component.extract_from_service(service)

        option = service.data.get(ATTR_OPTION)

        if option is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_OPTION, ATTR_OPTION)

        else:
            for target_select in target_selects:
                target_select.select(option)

            for target_select in target_selects:
                if target_select.should_poll:
                    target_select.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(
        DOMAIN, SERVICE_SET_OPTION, option_service,
        descriptions.get(SERVICE_SET_OPTION))

    return True


class SelectableDevice(Entity):
    """ Represents a select within Home Assistant. """

    @property
    def state(self):
        """ Returns the selected option of the entity. """
        return None

    @property
    def options(self):
        """ Returns the list of available options for this entity. """
        return []

    def select(self, option, **kwargs):
        """ Select the option 'option' for this entity. """
        pass

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        data = {
            ATTR_OPTIONS: self.options,
        }

        return data
