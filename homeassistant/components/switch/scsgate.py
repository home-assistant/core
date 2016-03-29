"""
Support for SCSGate switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.scsgate/
"""
import logging

import homeassistant.components.scsgate as scsgate
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import ATTR_ENTITY_ID

DEPENDENCIES = ['scsgate']


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the SCSGate switches."""
    logger = logging.getLogger(__name__)

    _setup_traditional_switches(
        logger=logger,
        config=config,
        add_devices_callback=add_devices_callback)

    _setup_scenario_switches(
        logger=logger,
        config=config,
        hass=hass)


def _setup_traditional_switches(logger, config, add_devices_callback):
    """Add traditional SCSGate switches."""
    traditional = config.get('traditional')
    switches = []

    if traditional:
        for _, entity_info in traditional.items():
            if entity_info['scs_id'] in scsgate.SCSGATE.devices:
                continue

            logger.info(
                "Adding %s scsgate.traditional_switch", entity_info['name'])

            name = entity_info['name']
            scs_id = entity_info['scs_id']

            switch = SCSGateSwitch(
                name=name,
                scs_id=scs_id,
                logger=logger)
            switches.append(switch)

    add_devices_callback(switches)
    scsgate.SCSGATE.add_devices_to_register(switches)


def _setup_scenario_switches(logger, config, hass):
    """Add only SCSGate scenario switches."""
    scenario = config.get("scenario")

    if scenario:
        for _, entity_info in scenario.items():
            if entity_info['scs_id'] in scsgate.SCSGATE.devices:
                continue

            logger.info(
                "Adding %s scsgate.scenario_switch", entity_info['name'])

            name = entity_info['name']
            scs_id = entity_info['scs_id']

            switch = SCSGateScenarioSwitch(
                name=name,
                scs_id=scs_id,
                logger=logger,
                hass=hass)
            scsgate.SCSGATE.add_device(switch)


class SCSGateSwitch(SwitchDevice):
    """Representation of a SCSGate switch."""

    def __init__(self, scs_id, name, logger):
        """Initialize the switch."""
        self._name = name
        self._scs_id = scs_id
        self._toggled = False
        self._logger = logger

    @property
    def scs_id(self):
        """Return the SCS ID."""
        return self._scs_id

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._toggled

    def turn_on(self, **kwargs):
        """Turn the device on."""
        from scsgate.tasks import ToggleStatusTask

        scsgate.SCSGATE.append_task(
            ToggleStatusTask(
                target=self._scs_id,
                toggled=True))

        self._toggled = True
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        from scsgate.tasks import ToggleStatusTask

        scsgate.SCSGATE.append_task(
            ToggleStatusTask(
                target=self._scs_id,
                toggled=False))

        self._toggled = False
        self.update_ha_state()

    def process_event(self, message):
        """Handle a SCSGate message related with this switch."""
        if self._toggled == message.toggled:
            self._logger.info(
                "Switch %s, ignoring message %s because state already active",
                self._scs_id, message)
            # Nothing changed, ignoring
            return

        self._toggled = message.toggled
        self.update_ha_state()

        command = "off"
        if self._toggled:
            command = "on"

        self.hass.bus.fire(
            'button_pressed', {
                ATTR_ENTITY_ID: self._scs_id,
                'state': command
            }
        )


class SCSGateScenarioSwitch:
    """Provides a SCSGate scenario switch.

    This switch is always in a 'off" state, when toggled it's used to trigger
    events.
    """

    def __init__(self, scs_id, name, logger, hass):
        """Initialize the scenario."""
        self._name = name
        self._scs_id = scs_id
        self._logger = logger
        self._hass = hass

    @property
    def scs_id(self):
        """Return the SCS ID."""
        return self._scs_id

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    def process_event(self, message):
        """Handle a SCSGate message related with this switch."""
        from scsgate.messages import StateMessage, ScenarioTriggeredMessage

        if isinstance(message, StateMessage):
            scenario_id = message.bytes[4]
        elif isinstance(message, ScenarioTriggeredMessage):
            scenario_id = message.scenario
        else:
            self._logger.warn(
                "Scenario switch: received unknown message %s",
                message)
            return

        self._hass.bus.fire(
            'scenario_switch_triggered', {
                ATTR_ENTITY_ID: int(self._scs_id),
                'scenario_id': int(scenario_id, 16)
            }
        )
