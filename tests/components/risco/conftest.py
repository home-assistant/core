"""Fixtures for Risco tests."""
from unittest.mock import MagicMock, PropertyMock, patch

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

from .util import TEST_SITE_NAME, TEST_SITE_UUID, zone_mock

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
def two_zone_cloud():
    """Fixture to mock alarm with two zones."""
    zone_mocks = {0: zone_mock(), 1: zone_mock()}
    alarm_mock = MagicMock()
    with patch.object(
        zone_mocks[0], "id", new_callable=PropertyMock(return_value=0)
    ), patch.object(
        zone_mocks[0], "name", new_callable=PropertyMock(return_value="Zone 0")
    ), patch.object(
        zone_mocks[0], "bypassed", new_callable=PropertyMock(return_value=False)
    ), patch.object(
        zone_mocks[1], "id", new_callable=PropertyMock(return_value=1)
    ), patch.object(
        zone_mocks[1], "name", new_callable=PropertyMock(return_value="Zone 1")
    ), patch.object(
        zone_mocks[1], "bypassed", new_callable=PropertyMock(return_value=False)
    ), patch.object(
        alarm_mock,
        "zones",
        new_callable=PropertyMock(return_value=zone_mocks),
    ), patch(
        "homeassistant.components.risco.RiscoCloud.get_state",
        return_value=alarm_mock,
    ):
        yield zone_mocks


@pytest.fixture
def two_zone_local():
    """Fixture to mock alarm with two zones."""
    zone_mocks = {0: zone_mock(), 1: zone_mock()}
    with patch.object(
        zone_mocks[0], "id", new_callable=PropertyMock(return_value=0)
    ), patch.object(
        zone_mocks[0], "name", new_callable=PropertyMock(return_value="Zone 0")
    ), patch.object(
        zone_mocks[0], "alarmed", new_callable=PropertyMock(return_value=False)
    ), patch.object(
        zone_mocks[0], "bypassed", new_callable=PropertyMock(return_value=False)
    ), patch.object(
        zone_mocks[0], "armed", new_callable=PropertyMock(return_value=False)
    ), patch.object(
        zone_mocks[1], "id", new_callable=PropertyMock(return_value=1)
    ), patch.object(
        zone_mocks[1], "name", new_callable=PropertyMock(return_value="Zone 1")
    ), patch.object(
        zone_mocks[1], "alarmed", new_callable=PropertyMock(return_value=False)
    ), patch.object(
        zone_mocks[1], "bypassed", new_callable=PropertyMock(return_value=False)
    ), patch.object(
        zone_mocks[1], "armed", new_callable=PropertyMock(return_value=False)
    ), patch(
        "homeassistant.components.risco.RiscoLocal.partitions",
        new_callable=PropertyMock(return_value={}),
    ), patch(
        "homeassistant.components.risco.RiscoLocal.zones",
        new_callable=PropertyMock(return_value=zone_mocks),
    ):
        yield zone_mocks


@pytest.fixture
def options():
    """Fixture for default (empty) options."""
    return {}


@pytest.fixture
def events():
    """Fixture for default (empty) events."""
    return []


@pytest.fixture
def cloud_config_entry(hass, options):
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
async def setup_risco_cloud(hass, cloud_config_entry, events):
    """Set up a Risco integration for testing."""
    with patch(
        "homeassistant.components.risco.RiscoCloud.login",
        return_value=True,
    ), patch(
        "homeassistant.components.risco.RiscoCloud.site_uuid",
        new_callable=PropertyMock(return_value=TEST_SITE_UUID),
    ), patch(
        "homeassistant.components.risco.RiscoCloud.site_name",
        new_callable=PropertyMock(return_value=TEST_SITE_NAME),
    ), patch(
        "homeassistant.components.risco.RiscoCloud.close"
    ), patch(
        "homeassistant.components.risco.RiscoCloud.get_events",
        return_value=events,
    ):
        await hass.config_entries.async_setup(cloud_config_entry.entry_id)
        await hass.async_block_till_done()

        yield cloud_config_entry


@pytest.fixture
def local_config_entry(hass, options):
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
async def setup_risco_local(hass, local_config_entry):
    """Set up a local Risco integration for testing."""
    with patch(
        "homeassistant.components.risco.RiscoLocal.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.risco.RiscoLocal.id",
        new_callable=PropertyMock(return_value=TEST_SITE_UUID),
    ), patch(
        "homeassistant.components.risco.RiscoLocal.disconnect"
    ):
        await hass.config_entries.async_setup(local_config_entry.entry_id)
        await hass.async_block_till_done()

        yield local_config_entry
