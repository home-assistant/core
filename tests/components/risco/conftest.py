"""Fixtures for Risco tests."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.risco.const import DOMAIN, TYPE_LOCAL
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_PORT,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .util import TEST_SITE_NAME, TEST_SITE_UUID, system_mock, zone_mock

from tests.common import MockConfigEntry

TEST_CLOUD_CONFIG = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_PIN: "1234",
}
TEST_LOCAL_CONFIG = {
    CONF_TYPE: TYPE_LOCAL,
    CONF_HOST: "test-host",
    CONF_PORT: 5004,
    CONF_PIN: "1234",
}


@pytest.fixture
def cloud_alarm_mock() -> MagicMock:
    """Fixture to provide the cloud alarm mock for state handler callbacks."""
    return MagicMock()


@pytest.fixture
def two_zone_cloud(cloud_alarm_mock: MagicMock):
    """Fixture to mock alarm with two zones."""
    zone_mocks = {0: zone_mock(), 1: zone_mock()}
    with (
        patch.object(zone_mocks[0], "id", new_callable=PropertyMock(return_value=0)),
        patch.object(
            zone_mocks[0], "name", new_callable=PropertyMock(return_value="Zone 0")
        ),
        patch.object(
            zone_mocks[0], "bypassed", new_callable=PropertyMock(return_value=False)
        ),
        patch.object(zone_mocks[1], "id", new_callable=PropertyMock(return_value=1)),
        patch.object(
            zone_mocks[1], "name", new_callable=PropertyMock(return_value="Zone 1")
        ),
        patch.object(
            zone_mocks[1], "bypassed", new_callable=PropertyMock(return_value=False)
        ),
        patch.object(
            cloud_alarm_mock,
            "zones",
            new_callable=PropertyMock(return_value=zone_mocks),
        ),
        patch(
            "homeassistant.components.risco.RiscoCloud.get_state",
            return_value=cloud_alarm_mock,
        ),
    ):
        yield zone_mocks


@pytest.fixture
def two_zone_local():
    """Fixture to mock alarm with two zones."""
    zone_mocks = {0: zone_mock(), 1: zone_mock()}
    system = system_mock()
    with (
        patch.object(zone_mocks[0], "id", new_callable=PropertyMock(return_value=0)),
        patch.object(
            zone_mocks[0], "name", new_callable=PropertyMock(return_value="Zone 0")
        ),
        patch.object(
            zone_mocks[0], "alarmed", new_callable=PropertyMock(return_value=False)
        ),
        patch.object(
            zone_mocks[0], "bypassed", new_callable=PropertyMock(return_value=False)
        ),
        patch.object(
            zone_mocks[0], "armed", new_callable=PropertyMock(return_value=False)
        ),
        patch.object(zone_mocks[1], "id", new_callable=PropertyMock(return_value=1)),
        patch.object(
            zone_mocks[1], "name", new_callable=PropertyMock(return_value="Zone 1")
        ),
        patch.object(
            zone_mocks[1], "alarmed", new_callable=PropertyMock(return_value=False)
        ),
        patch.object(
            zone_mocks[1], "bypassed", new_callable=PropertyMock(return_value=False)
        ),
        patch.object(
            zone_mocks[1], "armed", new_callable=PropertyMock(return_value=False)
        ),
        patch.object(
            system, "name", new_callable=PropertyMock(return_value=TEST_SITE_NAME)
        ),
        patch(
            "homeassistant.components.risco.RiscoLocal.partitions",
            new_callable=PropertyMock(return_value={}),
        ),
        patch(
            "homeassistant.components.risco.RiscoLocal.zones",
            new_callable=PropertyMock(return_value=zone_mocks),
        ),
        patch(
            "homeassistant.components.risco.RiscoLocal.system",
            new_callable=PropertyMock(return_value=system),
        ),
    ):
        yield zone_mocks


@pytest.fixture
def options() -> dict[str, Any]:
    """Fixture for default (empty) options."""
    return {}


@pytest.fixture
def cloud_config_entry(hass: HomeAssistant, options: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a cloud config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CLOUD_CONFIG,
        options=options,
        unique_id=TEST_CLOUD_CONFIG[CONF_USERNAME],
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def login_with_error(exception):
    """Fixture to simulate error on login."""
    with patch(
        "homeassistant.components.risco.RiscoCloud.login",
        side_effect=exception,
    ):
        yield


@pytest.fixture
def mock_cloud_login() -> AsyncMock:
    """Fixture to mock RiscoCloud.login and expose it for call count checks."""
    with patch(
        "homeassistant.components.risco.RiscoCloud.login",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_cloud_state_handler() -> MagicMock:
    """Fixture to capture state handler callbacks registered with the library."""
    with patch("homeassistant.components.risco.RiscoCloud.add_state_handler") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture
def mock_cloud_event_handler() -> MagicMock:
    """Fixture to capture event handler callbacks registered with the library."""
    with patch("homeassistant.components.risco.RiscoCloud.add_event_handler") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture
async def setup_risco_cloud(
    hass: HomeAssistant,
    cloud_config_entry: MockConfigEntry,
    mock_cloud_login: AsyncMock,
    mock_cloud_state_handler: MagicMock,
    mock_cloud_event_handler: MagicMock,
) -> AsyncGenerator[MockConfigEntry]:
    """Set up a Risco integration for testing."""
    with (
        patch(
            "homeassistant.components.risco.RiscoCloud.site_uuid",
            new_callable=PropertyMock(return_value=TEST_SITE_UUID),
        ),
        patch(
            "homeassistant.components.risco.RiscoCloud.site_name",
            new_callable=PropertyMock(return_value=TEST_SITE_NAME),
        ),
        patch(
            "homeassistant.components.risco.RiscoCloud.close",
        ),
        patch(
            "homeassistant.components.risco.RiscoCloud.subscribe_states",
            new_callable=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(cloud_config_entry.entry_id)
        await hass.async_block_till_done()

        yield cloud_config_entry


@pytest.fixture
def local_config_entry(hass: HomeAssistant, options: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a local config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_LOCAL_CONFIG, options=options
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def connect_with_error(exception):
    """Fixture to simulate error on connect."""
    with patch(
        "homeassistant.components.risco.RiscoLocal.connect",
        side_effect=exception,
    ):
        yield


@pytest.fixture
async def setup_risco_local(
    hass: HomeAssistant, local_config_entry: MockConfigEntry
) -> AsyncGenerator[MockConfigEntry]:
    """Set up a local Risco integration for testing."""
    with (
        patch(
            "homeassistant.components.risco.RiscoLocal.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.risco.RiscoLocal.id",
            new_callable=PropertyMock(return_value=TEST_SITE_UUID),
        ),
        patch(
            "homeassistant.components.risco.RiscoLocal.disconnect",
        ),
    ):
        await hass.config_entries.async_setup(local_config_entry.entry_id)
        await hass.async_block_till_done()

        yield local_config_entry
