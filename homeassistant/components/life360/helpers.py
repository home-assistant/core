"""Life360 integration helpers."""
from life360 import Life360


def get_api(authorization=None):
    """Create Life360 api object."""
    return Life360(timeout=3.05, max_retries=2, authorization=authorization)
