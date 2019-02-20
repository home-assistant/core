"""
Allow to configure a SCSGate cover.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.scsgate/
"""
import logging

import voluptuous as vol

from homeassistant.components import scsgate
from homeassistant.components.cover import (CoverDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_DEVICES, CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['scsgate']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES): vol.Schema({cv.slug: scsgate.SCSGATE_SCHEMA}),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the SCSGate cover."""
    devices = config.get(CONF_DEVICES)
    covers = []
    logger = logging.getLogger(__name__)

    if devices:
        for _, entity_info in devices.items():
            if entity_info[scsgate.CONF_SCS_ID] in scsgate.SCSGATE.devices:
                continue

            name = entity_info[CONF_NAME]
            scs_id = entity_info[scsgate.CONF_SCS_ID]

            logger.info("Adding %s scsgate.cover", name)

            cover = SCSGateCover(name=name, scs_id=scs_id, logger=logger)
            scsgate.SCSGATE.add_device(cover)
            covers.append(cover)

    add_entities(covers)


class SCSGateCover(CoverDevice):
    """Representation of SCSGate cover."""

    def __init__(self, scs_id, name, logger):
        """Initialize the cover."""
        self._scs_id = scs_id
        self._name = name
        self._logger = logger

    @property
    def scs_id(self):
        """Return the SCSGate ID."""
        return self._scs_id

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return None

    def open_cover(self, **kwargs):
        """Move the cover."""
        from scsgate.tasks import RaiseRollerShutterTask

        scsgate.SCSGATE.append_task(
            RaiseRollerShutterTask(target=self._scs_id))

    def close_cover(self, **kwargs):
        """Move the cover down."""
        from scsgate.tasks import LowerRollerShutterTask

        scsgate.SCSGATE.append_task(
            LowerRollerShutterTask(target=self._scs_id))

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        from scsgate.tasks import HaltRollerShutterTask

        scsgate.SCSGATE.append_task(HaltRollerShutterTask(target=self._scs_id))

    def process_event(self, message):
        """Handle a SCSGate message related with this cover."""
        self._logger.debug("Cover %s, got message %s",
                           self._scs_id, message.toggled)
