"""Fixtures for FileUpload integration."""
from io import StringIO

import pytest


@pytest.fixture
def large_file_io() -> StringIO:
    """Generate a large file on the fly."""
    file = StringIO("")
    for _ in range(10000):
        file.write(
            "Home Assistant is awesome. Open source home automation that puts local control and privacy first."
        )
    file.seek(0)
    return file
