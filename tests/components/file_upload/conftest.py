"""Fixtures for FileUpload integration."""

from io import StringIO

import pytest


@pytest.fixture
def large_file_io() -> StringIO:
    """Generate a file on the fly. Simulates a large file."""
    return StringIO(
        2
        * "Home Assistant is awesome. Open source home automation that puts local control and privacy first."
    )
