"""Support for Honeywell evohome (EMEA/EU-based systems only).

Support for a temperature control system (TCS, controller) with 0+ heating
zones (e.g. TRVs, relays) and, optionally, a DHW controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/evohome/
"""

import logging

from homeassistant.components.evohome import (
    EvoController,

    DATA_EVOHOME,
    CONF_LOCATION_IDX,
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create a Honeywell (EMEA/EU) evohome CH/DHW system.

    An evohome system consists of: a controller, with 0-12 heating zones (e.g.
    TRVs, relays) and, optionally, a DHW controller (a HW boiler).

    Here, we add the controller, and the zones (if there are any).
    """
    client = hass.data[DATA_EVOHOME]['client']
    loc_idx = hass.data[DATA_EVOHOME]['params'][CONF_LOCATION_IDX]

# Collect the (master) controller - evohomeclient has no defined way of
# accessing non-default location other than using the protected member
    tcs_obj_ref = client.locations[loc_idx]._gateways[0]._control_systems[0]    # noqa E501; pylint: disable=protected-access

    _LOGGER.debug(
        "setup_platform(): Found Controller [idx=%s]: id: %s [%s], type: %s",
        loc_idx,
        tcs_obj_ref.systemId,
        tcs_obj_ref.location.name,
        tcs_obj_ref.modelType
    )
    master = EvoController(hass, client, tcs_obj_ref)
    add_entities([master], update_before_add=False)

    return True
