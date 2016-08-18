"""Setup some common test helper things."""
import functools
import logging

from homeassistant import util
from homeassistant.util import location

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


def test_real(func):
    """Force a function to require a keyword _test_real to be passed in."""
    @functools.wraps(func)
    def guard_func(*args, **kwargs):
        real = kwargs.pop('_test_real', None)

        if not real:
            raise Exception('Forgot to mock or pass "_test_real=True" to %s',
                            func.__name__)

        return func(*args, **kwargs)

    return guard_func

# Guard a few functions that would make network connections
location.detect_location_info = test_real(location.detect_location_info)
location.elevation = test_real(location.elevation)
util.get_local_ip = lambda: '127.0.0.1'
