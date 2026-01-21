"""Test fixtures for the Dexcom integration."""

from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

from pydexcom import GlucoseReading, Region
import pytest

from homeassistant.components.dexcom.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

TEST_USERNAME = "username"
TEST_PASSWORD = "password"
TEST_REGION = Region.US
TEST_ACCOUNT_ID = "99999999-9999-9999-9999-999999999999"
TEST_SESSION_ID = "55555555-5555-5555-5555-555555555555"
TEST_SESSION_ID_EXPIRED = "33333333-3333-3333-3333-333333333333"

CONFIG_V1 = {
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
    "server": "us",
}

CONFIG_V2 = {
    CONF_USERNAME: TEST_USERNAME,
    CONF_PASSWORD: TEST_PASSWORD,
    CONF_REGION: TEST_REGION,
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TEST_USERNAME,
        unique_id=TEST_ACCOUNT_ID,
        data=CONFIG_V2,
        version=2,
    )


@pytest.fixture
def mock_dexcom_gen() -> Generator[MagicMock]:
    """Mock `Dexcom` generator."""
    with (
        patch(
            "homeassistant.components.dexcom.config_flow.Dexcom",
            autospec=True,
        ) as mock_dexcom,
        patch(
            "homeassistant.components.dexcom.Dexcom",
            new=mock_dexcom,
        ),
    ):
        yield mock_dexcom


@pytest.fixture
def mock_dexcom(mock_dexcom_gen: Generator[MagicMock]) -> MagicMock:
    """Mock `Dexcom`."""
    dexcom = mock_dexcom_gen.return_value
    dexcom.username = TEST_USERNAME
    dexcom.password = TEST_PASSWORD
    dexcom.region = TEST_REGION
    dexcom.account_id = TEST_ACCOUNT_ID
    dexcom.session_id = TEST_SESSION_ID
    return dexcom


@pytest.fixture
def mock_glucose_reading() -> GlucoseReading:
    """Mock `GlucoseReading`."""
    return GlucoseReading(json.loads(load_fixture("data.json", "dexcom")))


async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up the Dexcom integration in Home Assistant."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
