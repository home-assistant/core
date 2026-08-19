"""Fixtures for Hot Spring integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from hotspring import Heater, Spa, SpaBrand, SpaInfo, Versions
import pytest

from homeassistant.components.hotspring.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="AA:BB:CC:DD:EE:FF",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.hotspring.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def device_fixture() -> Spa:
    """Return the device fixture for a Hot Spring spa."""
    spa = MagicMock(spec=Spa)
    spa.info = SpaInfo(
        hostname="ConnectedSpa_DDEEFF",
        root_topic="mySpaAABBCCDDEEFF",
        sna_ready=True,
        brand=SpaBrand.HOTSPRING,
        brand_name="Hot Spring",
        collection="Highlife",
        model_name="Relay",
        brand_id="1",
        collection_id="1",
        model_id="1",
        volume=335,
    )
    spa.versions = Versions(
        control_box="3.0.0",
        control_panel="2.0.0",
        fwss="",
        fwiq="",
        btxr="",
        cool_zone="",
        wifi_dongle="1.0.0",
        amp="",
        dosing="",
        logolight="",
    )
    heater = MagicMock(spec=Heater)
    heater.current_temperature = 102.0
    heater.set_temperature = 104.0
    heater.is_on = True
    spa.heater = heater
    return spa


@pytest.fixture
def mock_hotspring(device_fixture: Spa) -> Generator[MagicMock]:
    """Return a mocked HotSpring client."""
    with (
        patch(
            "homeassistant.components.hotspring.coordinator.HotSpring", autospec=True
        ) as hotspring_mock,
        patch(
            "homeassistant.components.hotspring.config_flow.HotSpring",
            new=hotspring_mock,
        ),
    ):
        client = hotspring_mock.return_value
        client.update.return_value = device_fixture
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> MockConfigEntry:
    """Set up the Hot Spring integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
