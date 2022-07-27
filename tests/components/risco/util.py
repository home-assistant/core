"""Utilities for Risco tests."""
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from pytest import fixture

from homeassistant.components.risco.const import DOMAIN, TYPE_LOCAL
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_PORT,
    CONF_TYPE,
    CONF_USERNAME,
)

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
TEST_SITE_UUID = "test-site-uuid"
TEST_SITE_NAME = "test-site-name"


async def setup_risco_cloud(hass, events=[], options={}):
    """Set up a Risco integration for testing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_CLOUD_CONFIG, options=options
    )
    config_entry.add_to_hass(hass)

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
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def setup_risco_local(hass, options={}):
    """Set up a Risco integration for testing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_LOCAL_CONFIG, options=options
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.risco.RiscoLocal.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.risco.RiscoLocal.id",
        new_callable=PropertyMock(return_value=TEST_SITE_UUID),
    ), patch(
        "homeassistant.components.risco.RiscoLocal.disconnect"
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


def _zone_mock():
    return MagicMock(
        triggered=False, bypassed=False, bypass=AsyncMock(return_value=True)
    )


@fixture
def two_zone_cloud():
    """Fixture to mock alarm with two zones."""
    zone_mocks = {0: _zone_mock(), 1: _zone_mock()}
    alarm_mock = MagicMock()
    with patch.object(
        zone_mocks[0], "id", new_callable=PropertyMock(return_value=0)
    ), patch.object(
        zone_mocks[0], "name", new_callable=PropertyMock(return_value="Zone 0")
    ), patch.object(
        zone_mocks[1], "id", new_callable=PropertyMock(return_value=1)
    ), patch.object(
        zone_mocks[1], "name", new_callable=PropertyMock(return_value="Zone 1")
    ), patch.object(
        alarm_mock,
        "zones",
        new_callable=PropertyMock(return_value=zone_mocks),
    ), patch(
        "homeassistant.components.risco.RiscoCloud.get_state",
        return_value=alarm_mock,
    ):
        yield zone_mocks


@fixture
def two_zone_local():
    """Fixture to mock alarm with two zones."""
    zone_mocks = {0: _zone_mock(), 1: _zone_mock()}
    with patch.object(
        zone_mocks[0], "id", new_callable=PropertyMock(return_value=0)
    ), patch.object(
        zone_mocks[0], "name", new_callable=PropertyMock(return_value="Zone 0")
    ), patch.object(
        zone_mocks[1], "id", new_callable=PropertyMock(return_value=1)
    ), patch.object(
        zone_mocks[1], "name", new_callable=PropertyMock(return_value="Zone 1")
    ), patch(
        "homeassistant.components.risco.RiscoLocal.partitions",
        new_callable=PropertyMock(return_value={}),
    ), patch(
        "homeassistant.components.risco.RiscoLocal.zones",
        new_callable=PropertyMock(return_value=zone_mocks),
    ):
        yield zone_mocks
