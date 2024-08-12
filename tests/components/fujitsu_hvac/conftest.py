"""Common fixtures for the Fujitsu HVAC (based on Ayla IOT) tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.fujitsu_hvac.const import CONF_EUROPE, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

TEST_DEVICE_NAME = "Test device"
TEST_DEVICE_SERIAL = "testserial"
TEST_USERNAME = "test-username"
TEST_PASSWORD = "test-password"

TEST_USERNAME2 = "test-username2"
TEST_PASSWORD2 = "test-password2"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fujitsu_hvac.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_ayla_api(request: pytest.FixtureRequest) -> Generator[AsyncMock]:
    """Override async_sign_in in AylaApi to either do nothing or raise an exception."""
    mymock = MagicMock()
    mymock.async_sign_in = AsyncMock(side_effect=getattr(request, "param", None))

    with (
        patch("ayla_iot_unofficial.ayla_iot_unofficial.AylaApi", return_value=mymock),
    ):
        yield mymock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a regular config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_EUROPE: False,
        },
    )
