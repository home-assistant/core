"""
Sensor platform representing an Azure Virtual Machine.

For more details about this sensor platform, please refer to the documentation
at https://home-assistant.io/components/sensor.azure/
"""

from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.components.azure import DOMAIN as AZURE_DOMAIN

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['azure']

CONF_VIRTUAL_MACHINE = 'virtual_machine'
CONF_RESOURCE_GROUP = 'resource_group'

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE_GROUP): cv.string,
    vol.Optional(CONF_VIRTUAL_MACHINE, default=None): cv.string,
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Add the azure vm sensor."""
    virtual_machine = config.get(CONF_VIRTUAL_MACHINE)
    if virtual_machine is not None:
        add_entities([AzureVmSensor(hass.data[AZURE_DOMAIN], config)])


class AzureVmSensor(Entity):
    """Representation of an Azure virutal machine."""

    def __init__(self, azure_subscription, config):
        """Initialize the sensor."""
        from azure.mgmt.compute import ComputeManagementClient

        self._azure_compute_client = ComputeManagementClient(
            azure_subscription.credentials, azure_subscription.subscription_id)
        self._name = config[CONF_VIRTUAL_MACHINE]
        self._resource_group = config[CONF_RESOURCE_GROUP]
        self._state = None

    @property
    def name(self):
        """Return the name of the azure vm."""
        return self._name

    @property
    def resource_group(self):
        """Return the resource group of the azure vm."""
        return self._resource_group

    @property
    def state(self):
        """Return the state of the azure vm."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend."""
        if self._state == "VM running":
            return 'mdi:server'
        return 'mdi:server-off'

    def update(self):
        """Retrieve latest state."""
        virtual_machine = self._azure_compute_client.virtual_machines.get(
            self._resource_group, self._name, expand='instanceView')
        self._state = virtual_machine.instance_view.statuses[1].display_status
        _LOGGER.debug("Status of azure vm %s - %s is %s", self._name,
                      self._resource_group, self._state)
