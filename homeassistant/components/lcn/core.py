"""Core dependencies for LCN component."""

import re

import voluptuous as vol

# definitions
CONF_SK_NUM_TRIES = 'sk_num_tries'
CONF_DIM_MODE = 'dim_mode'
CONF_OUTPUT = 'output'
CONF_TRANSITION = 'transition'
CONF_DIMMABLE = 'dimmable'
CONF_CONNECTIONS = 'connections'

DIM_MODES = ['steps50', 'steps200']
OUTPUT_PORTS = ['output1', 'output2', 'output3', 'output4']

# Regex for address validation
PATTERN_ADDRESS = re.compile('^((?P<conn_id>\\w+)\\.)?s?(?P<seg_id>\\d+)'
                             '\\.(?P<type>m|g)?(?P<id>\\d+)$')


def get_connection(connections, connection_id=None):
    """Return the connection object from list."""
    if connection_id is None:
        connection = connections[0]
    else:
        for connection in connections:
            if connection.connection_id == connection_id:
                break
        else:
            raise ValueError('Unknown connection_id.')
    return connection


def is_address(value):
    """Validate the given address string.

    Examples for S000M005 at myhome:
        myhome.s000.m005
        myhome.s0.m5
        myhome.0.5    ("m" is implicit if missing)

    Examples for s000g011
        myhome.0.g11
        myhome.s0.g11
    """
    matcher = PATTERN_ADDRESS.match(value)
    if matcher:
        is_group = (matcher.group('type') == 'g')
        addr = (int(matcher.group('seg_id')),
                int(matcher.group('id')),
                is_group)
        conn_id = matcher.group('conn_id')
        return addr, conn_id
    raise vol.error.Invalid('Not a valid address string.')
