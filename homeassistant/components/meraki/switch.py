"""Support switches from meraki"""
import logging
from datetime import timedelta
import voluptuous as vol

from meraki_sdk.controllers.switch_ports_controller import SwitchPortsController
from meraki_sdk.exceptions.api_exception import APIException
from meraki_sdk.meraki_sdk_client import MerakiSdkClient


from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY, CONF_DEVICE_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchDevice

# This is the last working version, please test before updating

_LOGGING = logging.getLogger(__name__)

DEFAULT_NAME = "Meraki Switch"
SCAN_INTERVAL = timedelta(seconds=30)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_API_KEY): cv.string, vol.Required(CONF_DEVICE_ID): cv.string}
)


async def async_get_switch_name(hass, client: MerakiSdkClient, serial: str):
    """this function will resolve the name of a switch"""
    organisations = await hass.async_add_executor_job(
        client.organizations.get_organizations
    )
    for org in organisations:
        networks = await hass.async_add_executor_job(
            client.networks.get_organization_networks, {"organization_id": org["id"]}
        )
        for network in networks:
            devices = await hass.async_add_executor_job(
                client.devices.get_network_devices, network["id"]
            )
            for device in devices:
                if device["serial"] == serial:
                    return device["name"]
    return None


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up meraki switches."""
    api_key = config.get(CONF_API_KEY)
    device_id = config.get(CONF_DEVICE_ID)

    client = MerakiSdkClient(api_key)

    switch_name = await async_get_switch_name(hass, client, device_id)

    switch_port_controller = client.switch_ports
    ports = []
    for switch_port in await hass.async_add_executor_job(
        switch_port_controller.get_device_switch_ports, device_id
    ):
        ports.append(
            MerakiSwitchPort(
                switch_port_controller, device_id, switch_port["number"], switch_name
            )
        )

    add_entities(ports)


class MerakiSwitchPort(SwitchDevice):
    """Meraki Switchport"""

    def __init__(
        self,
        switch_port_controller: SwitchPortsController,
        serial: str,
        port: int,
        switch_name: str = None,
    ):
        self._controller = switch_port_controller
        self._serial = serial
        self._switch_name = switch_name
        self._port = port
        self._unique_id = f"{serial}-{port}"
        self._name = f"{switch_name}-{port}"
        self._enabled = False

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this Switch device"""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._enabled

    def _update_port(self, enable: bool):
        collect = {}
        collect["serial"] = self._serial
        collect["number"] = self._port
        collect["update_device_switch_port"] = {"enabled": enable}
        try:
            self._controller.update_device_switch_port(collect)
            self._enabled = enable
        except APIException:
            _LOGGING.exception("Could not update switchport %s", self._unique_id)

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._update_port(enable=True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._update_port(enable=False)

    def update(self):
        """Updates the switchport"""
        collect = {}
        collect["serial"] = self._serial
        collect["number"] = self._port
        port = self._controller.get_device_switch_port(collect)
        if port["name"]:
            self._name = f"{self._switch_name}-{port['name']}"
        else:
            self._name = f"{self._switch_name}-{self._port}"
        self._enabled = port["enabled"]
