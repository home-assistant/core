"""Mock utilities that are async aware."""
import sys

if sys.version_info[:2] < (3, 8):
    from asynctest.mock import *  # noqa
    from asynctest.mock import CoroutineMock as AsyncMock  # noqa
else:
    from unittest.mock import *  # noqa
