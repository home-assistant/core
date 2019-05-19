"""Provides the constants needed for evohome."""

DOMAIN = 'evohome'
DATA_EVOHOME = 'data_' + DOMAIN

# the Zones' opmode; their state is usually 'inherited' from the TCS
EVO_FOLLOW = 'FollowSchedule'
EVO_TEMPOVER = 'TemporaryOverride'
EVO_PERMOVER = 'PermanentOverride'

# These are used only to help prevent E501 (line too long) violations.
GWS = 'gateways'
TCS = 'temperatureControlSystems'
