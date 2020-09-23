"""Test fixtures for the generic component."""

from io import BytesIO
from unittest.mock import Mock

from PIL import Image
import pytest


@pytest.fixture(scope="package")
def fakeimgbytes_png():
    """Fake image in RAM for testing."""
    buf = BytesIO()
    Image.new("RGB", (1, 1)).save(buf, format="PNG")
    yield bytes(buf.getbuffer())


@pytest.fixture(scope="package")
def fakeimgbytes_jpg():
    """Fake image in RAM for testing."""
    buf = BytesIO()  # fake image in ram for testing.
    Image.new("RGB", (1, 1)).save(buf, format="jpeg")
    yield bytes(buf.getbuffer())


@pytest.fixture(scope="package")
def fakeimgbytes_svg():
    """Fake image in RAM for testing."""
    yield bytes(
        '<svg xmlns="http://www.w3.org/2000/svg"><circle r="50"/></svg>',
        encoding="utf-8",
    )


@pytest.fixture(scope="package")
def fakevidcontainer():
    """Fake container object with .streams.video[0] != None."""
    fake = Mock()
    fake.streams.video = ["fakevid"]
    return fake
