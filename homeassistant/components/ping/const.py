"""Tracks devices by sending a ICMP echo request (ping)."""


# The ping binary and icmplib timeouts are not the same
# timeout. ping is an overall timeout, icmplib is the
# time since the data was sent.

# ping binary
PING_TIMEOUT = 3

# icmplib timeout
ICMP_TIMEOUT = 1

DOMAIN = "ping"

CONF_PING_COUNT = "count"
DEFAULT_PING_COUNT = 5

CONF_IMPORTED_BY = "imported_by"
