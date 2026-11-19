"""Constants for the TIS Control integration."""

from datetime import timedelta

DOMAIN = "tis_control"


# Modules that announce their changes are updated instantly; the poll only heals missed broadcasts.
POLL_INTERVAL = timedelta(seconds=30)

# How many status reads may wait for a reply at once. The bus runs at 9600 baud: a read and its reply take
# about 70 ms including the gap the gateway leaves between frames, so firing every module at once would
# leave the last replies of a 30-module site outside the read timeout. Four at a time keeps each read's
# wait near 0.3 s and still reads 60 modules in about 4 s, well inside POLL_INTERVAL.
MAX_PARALLEL_READS = 4

# Long enough to also catch modules that only show up through their own periodic broadcasts.
DISCOVERY_TIMEOUT = 8.0
