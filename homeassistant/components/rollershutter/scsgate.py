"""
homeassistant.components.rollershutter.scsgate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a SCSGate rollershutter.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rollershutter.scsgate/
"""
import logging
import homeassistant.components.scsgate as scsgate
from homeassistant.components.rollershutter import RollershutterDevice


DEPENDENCIES = ['scsgate']


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add the SCSGate swiches defined inside of the configuration file. """

    devices = config.get('devices')
    rollershutters = []
    logger = logging.getLogger(__name__)

    if devices:
        for _, entity_info in devices.items():
            if entity_info['scs_id'] in scsgate.SCSGATE.devices:
                continue

            logger.info("Adding %s scsgate.rollershutter", entity_info['name'])

            name = entity_info['name']
            scs_id = entity_info['scs_id']
            rollershutter = SCSGateRollerShutter(
                name=name,
                scs_id=scs_id,
                logger=logger)
            scsgate.SCSGATE.add_device(rollershutter)
            rollershutters.append(rollershutter)

    add_devices_callback(rollershutters)


# pylint: disable=too-many-arguments, too-many-instance-attributes
class SCSGateRollerShutter(RollershutterDevice):
    """ Represents a rollershutter that can be controlled using SCSGate. """
    def __init__(self, scs_id, name, logger):
        self._scs_id = scs_id
        self._name = name
        self._logger = logger

    @property
    def scs_id(self):
        """ SCSGate ID """
        return self._scs_id

    @property
    def should_poll(self):
        """ No polling needed """
        return False

    @property
    def name(self):
        """ The name of the rollershutter. """
        return self._name

    @property
    def current_position(self):
        """
        Return current position of rollershutter.
        None is unknown, 0 is closed, 100 is fully open.
        """
        return None

    def move_up(self, **kwargs):
        """ Move the rollershutter up. """
        from scsgate.tasks import RaiseRollerShutterTask

        scsgate.SCSGATE.append_task(
            RaiseRollerShutterTask(target=self._scs_id))

    def move_down(self, **kwargs):
        """ Move the rollershutter down. """
        from scsgate.tasks import LowerRollerShutterTask

        scsgate.SCSGATE.append_task(
            LowerRollerShutterTask(target=self._scs_id))

    def stop(self, **kwargs):
        """ Stop the device. """
        from scsgate.tasks import HaltRollerShutterTask

        scsgate.SCSGATE.append_task(HaltRollerShutterTask(target=self._scs_id))

    def process_event(self, message):
        """ Handle a SCSGate message related with this rollershutter """
        self._logger.debug(
            "Rollershutter %s, got message %s",
            self._scs_id, message.toggled)
