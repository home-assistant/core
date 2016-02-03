import betamax

from homeassistant.util import location

from .common import mock_detect_location_info

with betamax.Betamax.configure() as config:
    config.cassette_library_dir = 'tests/cassettes'

# This hits a 3rd party server. Always mock it.
location.detect_location_info = mock_detect_location_info
