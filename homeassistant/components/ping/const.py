"""Tracks devices by sending a ICMP echo request (ping)."""

from homeassistant.const import Platform

# The ping binary and icmplib timeouts are not the same
# timeout. ping is an overall timeout, icmplib is the
# time since the data was sent.

# ping binary
PING_TIMEOUT = 3

# icmplib timeout
ICMP_TIMEOUT = 1

PING_ATTEMPTS_COUNT = 3

DOMAIN = "ping"
PLATFORMS = [Platform.BINARY_SENSOR]

PING_PRIVS = "ping_privs"
