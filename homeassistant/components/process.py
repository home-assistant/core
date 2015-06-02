"""
homeassistant.components.process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to watch for specific processes running
on the host machine.

Author: Markus Stenberg <fingon@iki.fi>
"""
import logging
import os

from homeassistant.const import STATE_ON, STATE_OFF
import homeassistant.util as util

DOMAIN = 'process'
DEPENDENCIES = []
ENTITY_ID_FORMAT = DOMAIN + '.{}'

PS_STRING = 'ps awx'


def setup(hass, config):
    """ Sets up a check if specified processes are running.

        processes: dict mapping entity id to substring to search for
                   in process list.
    """

    # Deprecated as of 3/7/2015
    logging.getLogger(__name__).warning(
        "This component has been deprecated and will be removed in the future."
        " Please use sensor.systemmonitor with the process type")

    entities = {ENTITY_ID_FORMAT.format(util.slugify(pname)): pstring
                for pname, pstring in config[DOMAIN].items()}

    def update_process_states(time):
        """ Check ps for currently running processes and update states. """
        with os.popen(PS_STRING, 'r') as psfile:
            lines = list(psfile)

        for entity_id, pstring in entities.items():
            state = STATE_ON if any(pstring in l for l in lines) else STATE_OFF

            hass.states.set(entity_id, state)

    update_process_states(None)

    hass.track_time_change(update_process_states, second=[0, 30])

    return True
