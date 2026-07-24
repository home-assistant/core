"""Fixtures for TOLO Sauna integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from tololib import (
    AromaTherapySlot,
    Calefaction,
    LampMode,
    Model,
    ToloSettings,
    ToloStatus,
)

from homeassistant.components.tolo.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="TOLO Sauna",
        data={CONF_HOST: "127.0.0.1"},
        entry_id="01J00000000000000000000001",
    )


@pytest.fixture
def mock_tolo_status() -> ToloStatus:
    """Return a default mocked TOLO status."""
    return ToloStatus(
        power_on=True,
        current_temperature=45,
        power_timer=10,
        flow_in=True,
        flow_out=False,
        calefaction=Calefaction.HEAT,
        aroma_therapy_on=True,
        sweep_on=False,
        sweep_timer=0,
        lamp_on=True,
        water_level=2,
        fan_on=True,
        fan_timer=5,
        current_humidity=70,
        tank_temperature=50,
        model=Model.DOMESTIC,
        salt_bath_on=True,
        salt_bath_timer=15,
    )


@pytest.fixture
def mock_tolo_settings() -> ToloSettings:
    """Return a default mocked TOLO settings."""
    return ToloSettings(
        target_temperature=50,
        power_timer=30,
        aroma_therapy_slot=AromaTherapySlot.A,
        sweep_timer=None,
        fan_timer=20,
        target_humidity=80,
        salt_bath_timer=25,
        lamp_mode=LampMode.MANUAL,
    )


@pytest.fixture
def mock_tolo_client(
    mock_tolo_status: ToloStatus,
    mock_tolo_settings: ToloSettings,
) -> Generator[MagicMock]:
    """Return a mocked ToloClient."""
    with patch(
        "homeassistant.components.tolo.coordinator.ToloClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.get_status.return_value = mock_tolo_status
        client.get_settings.return_value = mock_tolo_settings
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
) -> MockConfigEntry:
    """Set up the TOLO integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
