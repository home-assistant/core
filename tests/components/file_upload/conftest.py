"""Fixtures for FileUpload integration."""
import tempfile

import pytest


@pytest.fixture
def large_file() -> tempfile.NamedTemporaryFile:
    """Generate a large file on the fly."""
    tmp_file = tempfile.NamedTemporaryFile()

    with open(tmp_file.name, "w") as fp:
        for _ in range(10000):
            fp.write(
                "Home Assistant is awesome. Open source home automation that puts local control and privacy first."
            )

    return tmp_file
