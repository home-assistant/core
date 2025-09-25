"""Common fixtures for the Cync tests."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, patch

from pycync import Cync, CyncHome
import pytest

from homeassistant.components.cync.const import (
    CONF_AUTHORIZE_STRING,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import MOCKED_EMAIL, MOCKED_USER

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture(autouse=True)
def auth_client():
    """Mock a pycync.Auth client."""
    with patch(
        "homeassistant.components.cync.config_flow.Auth", autospec=True
    ) as sc_class_mock:
        client_mock = sc_class_mock.return_value
        client_mock.user = MOCKED_USER
        client_mock.username = MOCKED_EMAIL
        yield client_mock


@pytest.fixture(autouse=True)
def cync_client():
    """Mock a pycync.Cync client."""
    with (
        patch(
            "homeassistant.components.cync.coordinator.Cync",
            spec=Cync,
        ) as cync_mock,
        patch(
            "homeassistant.components.cync.Cync",
            new=cync_mock,
        ),
    ):
        cync_mock.get_logged_in_user.return_value = MOCKED_USER

        home_fixture: CyncHome = CyncHome.from_dict(
            load_json_object_fixture("home.json", DOMAIN)
        )
        cync_mock.get_homes.return_value = [home_fixture]

        available_mock_devices = [
            device
            for device in home_fixture.get_flattened_device_list()
            if device.is_online
        ]
        cync_mock.get_devices.return_value = available_mock_devices

        cync_mock.create.return_value = cync_mock
        client_mock = cync_mock.return_value
        yield client_mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.cync.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a Cync config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCKED_EMAIL,
        unique_id=str(MOCKED_USER.user_id),
        data={
            CONF_USER_ID: MOCKED_USER.user_id,
            CONF_AUTHORIZE_STRING: "test_authorize_string",
            CONF_EXPIRES_AT: (time.time() * 1000) + 3600000,
            CONF_ACCESS_TOKEN: "test_token",
            CONF_REFRESH_TOKEN: "test_refresh_token",
        },
    )
