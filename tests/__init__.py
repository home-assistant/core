"""Test the initialization."""
import betamax

from homeassistant import util
from homeassistant.util import location

with betamax.Betamax.configure() as config:
    config.cassette_library_dir = 'tests/cassettes'

# Automatically called during different setups. Too often forgotten
# so mocked by default.
location.detect_location_info = lambda: location.LocationInfo(
    ip='1.1.1.1',
    country_code='US',
    country_name='United States',
    region_code='CA',
    region_name='California',
    city='San Diego',
    zip_code='92122',
    time_zone='America/Los_Angeles',
    latitude='2.0',
    longitude='1.0',
    use_fahrenheit=True,
)

location.elevation = lambda latitude, longitude: 0
util.get_local_ip = lambda: '127.0.0.1'
