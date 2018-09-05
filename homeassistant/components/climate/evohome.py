"""Support for Honeywell evohome (EMEA/EU-based systems only).

Support for a temperature control system (TCS, controller) with 0+ heating
zones (e.g. TRVs, relays) and, optionally, a DHW controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/evohome/
"""

import logging

from homeassistant.components.evohome import (
    EvoController,
    EvoZone,
    EvoBoiler,

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

# 1/3: Collect the (master) controller - evohomeclient has no defined way of
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
    slaves = []

# 2/3: Collect each (slave) Heating zone as a (climate component) device
    for zone_obj_ref in tcs_obj_ref._zones:                                     # noqa E501; pylint: disable=protected-access
        _LOGGER.debug(
            "setup_platform(): Found Zone device: id: %s, type: %s",
            zone_obj_ref.zoneId + " [" + zone_obj_ref.name + "]",
            zone_obj_ref.zone_type  # also has .zoneType (different)
        )
# We may not handle some zones correctly (e.g. UFH) - how to test for them?
#       if zone['zoneType'] in [ "RadiatorZone", "ZoneValves" ]:
        slaves.append(EvoZone(hass, client, zone_obj_ref))

# 3/3: Collect any (slave) DHW zone as a (climate component) device
    if tcs_obj_ref.hotwater:
        _LOGGER.debug(
            "setup_platform(): Found DHW device: id: %s, type: %s",
            tcs_obj_ref.hotwater.zoneId,  # also has .dhwId (same)
            tcs_obj_ref.hotwater.zone_type
        )
        slaves.append(EvoBoiler(hass, client, tcs_obj_ref.hotwater))

# for efficiency, add controller + all zones in a single call (add_devices)
    add_entities([master] + slaves, update_before_add=False)

    return True
