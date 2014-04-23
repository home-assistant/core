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
# Last modified: Wed Apr 23 23:48:13 2014 mstenber
# Edit time:     13 min
#
"""

Process watcher.

The arguments are <subentityname>=<substring to find in process list>

"""

import homeassistant as ha
from homeassistant.components import (STATE_ON, STATE_OFF)
import os

DOMAIN = 'process'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

PS_STRING='ps awx'

INTERVAL=30

def setup(bus, statemachine, **processes):
    _states = {}

    def _update_process_state(t, force_reload=False):
        with os.popen(PS_STRING, 'r') as f:
            lines = list(iter(f))
            for e, s in processes.items():
                found = False
                for line in lines:
                    if s in line:
                        found = True
                        break
                if _states.get(e, None) == found:
                    continue
                _states[e] = found
                entity_id = ENTITY_ID_FORMAT.format(e)
                state = found and STATE_ON or STATE_OFF
                statemachine.set_state(entity_id, state)

    _update_process_state(None, True)
    kwargs = {}
    if INTERVAL != ha.TIMER_INTERVAL:
        kwargs['second'] = [0, INTERVAL]
        assert INTERVAL > ha.TIMER_INTERVAL
    ha.track_time_change(bus, _update_process_state)
    return True
