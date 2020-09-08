"""Mock utilities that are async aware."""
import sys

if sys.version_info[:2] < (3, 8):
    from asynctest.mock import *  # noqa

    AsyncMock = CoroutineMock  # noqa: F405
else:
    from unittest.mock import *  # noqa
