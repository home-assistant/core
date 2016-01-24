"""
homeassistant.components.device_tracker.owntracks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
OwnTracks platform for the device tracker.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.owntracks/
"""
import json
import logging
import threading
from collections import defaultdict

import homeassistant.components.mqtt as mqtt
from homeassistant.const import (STATE_HOME, STATE_NOT_HOME)

DEPENDENCIES = ['mqtt']

REGIONS_ENTERED = defaultdict(list)

LOCATION_TOPIC = 'owntracks/+/+'
EVENT_TOPIC = 'owntracks/+/+/event'

_LOGGER = logging.getLogger(__name__)

LOCK = threading.Lock()


def setup_scanner(hass, config, see):
    """ Set up an OwnTracks tracker. """

    def owntracks_location_update(topic, payload, qos):
        """ MQTT message received. """

        # Docs on available data:
        # http://owntracks.org/booklet/tech/json/#_typelocation
        try:
            data = json.loads(payload)
        except ValueError:
            # If invalid JSON
            _LOGGER.error(
                'Unable to parse payload as JSON: %s', payload)
            return

        if not isinstance(data, dict) or data.get('_type') != 'location':
            return

        dev_id, kwargs = _parse_see_args(topic, data)

        # Block updates if we're in a region
        with LOCK:
            if REGIONS_ENTERED[dev_id]:
                _LOGGER.debug(
                    "location update ignored - inside region %s",
                    REGIONS_ENTERED[-1])
                return

            see(**kwargs)

    def owntracks_event_update(topic, payload, qos):
        """ MQTT event (geofences) received. """

        # Docs on available data:
        # http://owntracks.org/booklet/tech/json/#_typetransition
        try:
            data = json.loads(payload)
        except ValueError:
            # If invalid JSON
            _LOGGER.error(
                'Unable to parse payload as JSON: %s', payload)
            return

        if not isinstance(data, dict) or data.get('_type') != 'transition':
            return

        if data['desc'].lower() == 'home':
            location = STATE_HOME
        else:
            location = data['desc']

        dev_id, kwargs = _parse_see_args(topic, data)

        if data['event'] == 'enter':
            zone = hass.states.get("zone.{}".format(location))
            with LOCK:
                if zone is not None:
                    kwargs['location_name'] = location

                    regions = REGIONS_ENTERED[dev_id]
                    if location not in regions:
                        regions.append(location)
                    _LOGGER.info("Enter region %s", location)
                    _get_gps_from_zone(kwargs, zone)

                see(**kwargs)

        elif data['event'] == 'leave':
            current_location = hass.states.get(
                "device_tracker.{}".format(dev_id)).state

            regions = REGIONS_ENTERED[dev_id]
            if location in regions:
                regions.remove(location)
            new_region = regions[-1] if regions else None

            if not new_region:
                _LOGGER.info("Exit from %s to GPS", location)
                see(**kwargs)

                # if gps location didn't set new state, force to away
                current_location = hass.states.get(
                    "device_tracker.{}".format(dev_id)).state

                if current_location.lower() == location.lower():
                    kwargs['location_name'] = STATE_NOT_HOME
                    see(**kwargs)

                return

            if current_location.lower() == new_region.lower():
                _LOGGER.info("Exit from %s, still in %s",
                             location, current_location)
                return

            zone = hass.states.get("zone.{}".format(new_region))
            kwargs['location_name'] = new_region
            _get_gps_from_zone(kwargs, zone)
            _LOGGER.info("Exit from %s to %s", location, new_region)
            see(**kwargs)

        else:
            _LOGGER.error(
                'Misformatted mqtt msgs, _type=transition, event=%s',
                data['event'])
            return

    mqtt.subscribe(hass, LOCATION_TOPIC, owntracks_location_update, 1)

    mqtt.subscribe(hass, EVENT_TOPIC, owntracks_event_update, 1)

    return True


def _parse_see_args(topic, data):
    parts = topic.split('/')
    dev_id = '{}_{}'.format(parts[1], parts[2])
    host_name = parts[1]
    kwargs = {
        'dev_id': dev_id,
        'host_name': host_name,
        'gps': (data['lat'], data['lon'])
    }
    if 'acc' in data:
        kwargs['gps_accuracy'] = data['acc']
    if 'batt' in data:
        kwargs['battery'] = data['batt']
    return dev_id, kwargs


def _get_gps_from_zone(kwargs, zone):
    if zone is not None:
        kwargs['gps'] = (
            zone.attributes['latitude'],
            zone.attributes['longitude'])
        kwargs['gps_accuracy'] = 1
    return kwargs
