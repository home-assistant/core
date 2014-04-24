#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- Python -*-
#
# $Id: process.py $
#
# Author: Markus Stenberg <fingon@iki.fi>
#
# Copyright (c) 2014 Markus Stenberg
#
# Created:       Wed Apr 23 23:33:26 2014 mstenber
# Last modified: Thu Apr 24 17:13:04 2014 mstenber
# Edit time:     19 min
#
"""

Process watcher.

The arguments are <subentityname>=<substring to find in process list>

"""

from homeassistant.components import (STATE_ON, STATE_OFF)
import os

DOMAIN = 'process'
ENTITY_ID_FORMAT = DOMAIN + '.{}'
PS_STRING = 'ps awx'


def setup(hass, processes):
    """ Track local processes. """

    # pylint: disable=unused-argument
    def _update_process_state(time):
        """ Check ps for currently running processes. """
        with os.popen(PS_STRING, 'r') as psfile:
            lines = list(iter(psfile))
            for pname, pstring in processes.items():
                found = False
                for line in lines:
                    if pstring in line:
                        found = True
                        break
                entity_id = ENTITY_ID_FORMAT.format(pname)
                state = found and STATE_ON or STATE_OFF
                hass.states.set(entity_id, state)

    _update_process_state(None)
    hass.track_time_change(_update_process_state, second=[0, 30])
    return True
