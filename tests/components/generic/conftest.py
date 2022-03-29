"""Test fixtures for the generic component."""

from io import BytesIO
from unittest.mock import Mock, patch

from PIL import Image
import pytest
import respx

from homeassistant import config_entries, setup
from homeassistant.components.generic.const import DOMAIN


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


@pytest.fixture
def fakeimg_png(fakeimgbytes_png):
    """Set up respx to respond to test url with fake image bytes."""
    respx.get("http://127.0.0.1/testurl/1").respond(stream=fakeimgbytes_png)


@pytest.fixture(scope="package")
def mock_av_open():
    """Fake container object with .streams.video[0] != None."""
    fake = Mock()
    fake.streams.video = ["fakevid"]
    return patch(
        "homeassistant.components.generic.config_flow.av.open",
        return_value=fake,
    )


@pytest.fixture
async def user_flow(hass):
    """Initiate a user flow."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    return result
