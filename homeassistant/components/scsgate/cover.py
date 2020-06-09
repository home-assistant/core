"""Support for SCSGate covers."""
import logging

from scsgate.tasks import (
    HaltRollerShutterTask,
    LowerRollerShutterTask,
    RaiseRollerShutterTask,
)
import voluptuous as vol

from homeassistant.components.cover import PLATFORM_SCHEMA, CoverEntity
from homeassistant.const import CONF_DEVICES, CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import CONF_SCS_ID, DOMAIN, SCSGATE_SCHEMA

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_DEVICES): cv.schema_with_slug_keys(SCSGATE_SCHEMA)}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the SCSGate cover."""
    devices = config.get(CONF_DEVICES)
    covers = []
    logger = logging.getLogger(__name__)
    scsgate = hass.data[DOMAIN]

    if devices:
        for _, entity_info in devices.items():
            if entity_info[CONF_SCS_ID] in scsgate.devices:
                continue

            name = entity_info[CONF_NAME]
            scs_id = entity_info[CONF_SCS_ID]

            logger.info("Adding %s scsgate.cover", name)

            cover = SCSGateCover(
                name=name, scs_id=scs_id, logger=logger, scsgate=scsgate
            )
            scsgate.add_device(cover)
            covers.append(cover)

    add_entities(covers)


class SCSGateCover(CoverEntity):
    """Representation of SCSGate cover."""

    def __init__(self, scs_id, name, logger, scsgate):
        """Initialize the cover."""
        self._scs_id = scs_id
        self._name = name
        self._logger = logger
        self._scsgate = scsgate

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
        self._scsgate.append_task(RaiseRollerShutterTask(target=self._scs_id))

    def close_cover(self, **kwargs):
        """Move the cover down."""
        self._scsgate.append_task(LowerRollerShutterTask(target=self._scs_id))

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._scsgate.append_task(HaltRollerShutterTask(target=self._scs_id))

    def process_event(self, message):
        """Handle a SCSGate message related with this cover."""
        self._logger.debug("Cover %s, got message %s", self._scs_id, message.toggled)
