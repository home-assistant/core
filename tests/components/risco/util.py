"""Utilities for Risco tests."""
from pytest import fixture

from homeassistant.components.risco.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_USERNAME

from tests.async_mock import MagicMock, PropertyMock, patch
from tests.common import MockConfigEntry

TEST_CONFIG = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_PIN: "1234",
}
TEST_SITE_UUID = "test-site-uuid"
TEST_SITE_NAME = "test-site-name"


async def setup_risco(hass, options={}):
    """Set up a Risco integration for testing."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG, options=options)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.risco.RiscoAPI.login",
        return_value=True,
    ), patch(
        "homeassistant.components.risco.RiscoAPI.site_uuid",
        new_callable=PropertyMock(return_value=TEST_SITE_UUID),
    ), patch(
        "homeassistant.components.risco.RiscoAPI.site_name",
        new_callable=PropertyMock(return_value=TEST_SITE_NAME),
    ), patch(
        "homeassistant.components.risco.RiscoAPI.close"
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


def _zone_mock():
    return MagicMock(
        triggered=False,
        bypassed=False,
    )


@fixture
def two_zone_alarm():
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
        "homeassistant.components.risco.RiscoAPI.get_state",
        return_value=alarm_mock,
    ):
        yield alarm_mock
