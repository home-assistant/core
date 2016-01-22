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

import homeassistant.components.mqtt as mqtt
from homeassistant.const import (STATE_HOME, STATE_NOT_HOME)

DEPENDENCIES = ['mqtt']

STATE_OWNTRACKS_LAST_LOCATION = 'owntracks.location_{}'
STATE_OWNTRACKS_LAST_LOCATION_ATTR = {'hidden': True}

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

        dev_id, host_name = _parse_topic(topic)

        # Block updates if we're in a region
        LOCK.acquire()
        if _is_blocked(dev_id):
            _LOGGER.info("Owntracks update rejected - inside region")
            LOCK.release()
            return

        kwargs = {
            'dev_id': dev_id,
            'host_name': host_name,
            'gps': (data['lat'], data['lon']),
        }
        if 'acc' in data:
            kwargs['gps_accuracy'] = data['acc']
        if 'batt' in data:
            kwargs['battery'] = data['batt']

        see(**kwargs)
        LOCK.release()


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

        dev_id, host_name = _parse_topic(topic)

        if data['desc'].lower() == 'home':
            location = STATE_HOME
        else:
            location = data['desc']

        kwargs = {
            'dev_id': dev_id,
            'host_name': host_name,
            'gps': (data['lat'], data['lon'])
        }

        if 'acc' in data:
            kwargs['gps_accuracy'] = data['acc']

        if data['event'] == 'enter':
            zone = hass.states.get("zone.{}".format(location))
            LOCK.acquire()

            if zone is not None:
                kwargs['location_name'] = location
                _block_updates(dev_id, location)

                if data['t'] == 'b':
                    # For beacon events - the zone location is more
                    # accurate than gps
                    kwargs['gps'] = (
                        zone.attributes['latitude'],
                        zone.attributes['longitude'])
                    kwargs['gps_accuracy'] = 1

            see(**kwargs)
            LOCK.release()

            # Block location update while we're in a region

        elif data['event'] == 'leave':
            if not _valid_leave(dev_id, location):
                return

            see(**kwargs)

            _block_updates(dev_id, '')
            _force_state_change_if_needed(dev_id, location, kwargs)
        else:
            _LOGGER.error(
                'Misformatted mqtt msgs, _type=transition, event=%s',
                data['event'])
            return

    def _valid_leave(dev_id, location):
        """Check owntracks region is the right one to leave"""
        state_id = STATE_OWNTRACKS_LAST_LOCATION.format(dev_id)
        state = hass.states.get(state_id)
        if state is None:
            return True
        entry_location = state.state
        if entry_location == '':
            return True
        if entry_location.lower() == location.lower():
            return True
        _LOGGER.info("Owntracks leave region %s rejected - in region %s", location, entry_location)
        return False

    def _block_updates(dev_id, location):
        """ Add owntracks region to block location updates """
        hass.states.set(
            STATE_OWNTRACKS_LAST_LOCATION.format(dev_id),
            location,
            STATE_OWNTRACKS_LAST_LOCATION_ATTR)

    def _is_blocked(dev_id):
        """Block updates if we're in a region"""
        state = hass.states.get(
            STATE_OWNTRACKS_LAST_LOCATION.format(dev_id))
        blocked = (state is not None and
                  state.state != '')
        return blocked

    def _parse_topic(topic):
        parts = topic.split('/')
        dev_id = '{}_{}'.format(parts[1], parts[2])
        host_name = parts[1]
        return(dev_id, host_name)

    def _force_state_change_if_needed(dev_id, location, kwargs):
        # if gps location didn't set new state, force to away
        current_location = hass.states.get(
            "device_tracker.{}".format(dev_id)).state

        if current_location.lower() == location.lower():
            kwargs['location_name'] = STATE_NOT_HOME
            see(**kwargs)

    mqtt.subscribe(hass, LOCATION_TOPIC, owntracks_location_update, 1)

    mqtt.subscribe(hass, EVENT_TOPIC, owntracks_event_update, 1)

    return True
