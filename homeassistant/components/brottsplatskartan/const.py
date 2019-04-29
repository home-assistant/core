# coding: utf-8
"""Constants used by Brottsplatskartan components."""
from datetime import timedelta
import logging

_LOGGER = logging.getLogger('.')

ATTR_INCIDENTS = 'incidents'
ATTR_TITLE_TYPE = 'title_type'

CONF_AREA = 'area'
CONF_SENSOR = 'sensor'

DEFAULT_NAME = 'Brottsplatskartan'
DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

DOMAIN = 'brottsplatskartan'

SIGNAL_UPDATE_BPK = 'brottsplatskartan_update'
