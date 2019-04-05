"""Helpers for zwave specific config validation using voluptuous."""
import re
import voluptuous as vol

def zwave_network_key(value):
    """Validate a 16 byte value for zwave network keys."""
    regex = re.compile(r'(0x\w\w,\s?){15}0x\w\w')
    if not regex.match(value):
        raise vol.Invalid('Invalid Z-Wave network key')

    return str(value).lower()
