"""Setup mocks for the Plugwise integration tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from packaging.version import Version
from plugwise import PlugwiseData
import pytest

from homeassistant.components.plugwise.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


def _read_json(environment: str, call: str) -> dict[str, Any]:
    """Undecode the json data."""
    fixture = load_fixture(f"plugwise/{environment}/{call}.json")
    return json.loads(fixture)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My Plugwise",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_PASSWORD: "test-password",
            CONF_PORT: 80,
            CONF_USERNAME: "smile",
        },
        unique_id="smile98765",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.plugwise.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_smile_config_flow() -> Generator[MagicMock]:
    """Return a mocked Smile client."""
    with patch(
        "homeassistant.components.plugwise.config_flow.Smile",
        autospec=True,
    ) as smile_mock:
        smile = smile_mock.return_value
        smile.smile_hostname = "smile12345"
        smile.smile_model = "Test Model"
        smile.smile_model_id = "Test Model ID"
        smile.smile_name = "Test Smile Name"
        smile.connect.return_value = Version("4.3.2")
        yield smile


@pytest.fixture
def mock_smile_adam() -> Generator[MagicMock]:
    """Create a Mock Adam environment for testing exceptions."""
    chosen_env = "m_adam_multiple_devices_per_zone"

    with (
        patch(
            "homeassistant.components.plugwise.coordinator.Smile", autospec=True
        ) as smile_mock,
        patch(
            "homeassistant.components.plugwise.config_flow.Smile",
            new=smile_mock,
        ),
    ):
        smile = smile_mock.return_value

        smile.gateway_id = "fe799307f1624099878210aa0b9f1475"
        smile.heater_id = "90986d591dcd426cae3ec3e8111ff730"
        smile.smile_version = "3.0.15"
        smile.smile_type = "thermostat"
        smile.smile_hostname = "smile98765"
        smile.smile_model = "Gateway"
        smile.smile_model_id = "smile_open_therm"
        smile.smile_name = "Adam"
        smile.connect.return_value = Version("3.0.15")
        all_data = _read_json(chosen_env, "all_data")
        smile.async_update.return_value = PlugwiseData(
            all_data["devices"], all_data["gateway"]
        )

        yield smile


@pytest.fixture
def mock_smile_adam_2() -> Generator[MagicMock]:
    """Create a 2nd Mock Adam environment for testing exceptions."""
    chosen_env = "m_adam_heating"

    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "da224107914542988a88561b4452b0f6"
        smile.heater_id = "056ee145a816487eaa69243c3280f8bf"
        smile.smile_version = "3.6.4"
        smile.smile_type = "thermostat"
        smile.smile_hostname = "smile98765"
        smile.smile_model = "Gateway"
        smile.smile_model_id = "smile_open_therm"
        smile.smile_name = "Adam"
        smile.connect.return_value = Version("3.6.4")
        all_data = _read_json(chosen_env, "all_data")
        smile.async_update.return_value = PlugwiseData(
            all_data["devices"], all_data["gateway"]
        )

        yield smile


@pytest.fixture
def mock_smile_adam_3() -> Generator[MagicMock]:
    """Create a 3rd Mock Adam environment for testing exceptions."""
    chosen_env = "m_adam_cooling"

    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "da224107914542988a88561b4452b0f6"
        smile.heater_id = "056ee145a816487eaa69243c3280f8bf"
        smile.smile_version = "3.6.4"
        smile.smile_type = "thermostat"
        smile.smile_hostname = "smile98765"
        smile.smile_model = "Gateway"
        smile.smile_model_id = "smile_open_therm"
        smile.smile_name = "Adam"
        smile.connect.return_value = Version("3.6.4")
        all_data = _read_json(chosen_env, "all_data")
        smile.async_update.return_value = PlugwiseData(
            all_data["devices"], all_data["gateway"]
        )

        yield smile


@pytest.fixture
def mock_smile_adam_4() -> Generator[MagicMock]:
    """Create a 4th Mock Adam environment for testing exceptions."""
    chosen_env = "m_adam_jip"

    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "b5c2386c6f6342669e50fe49dd05b188"
        smile.heater_id = "e4684553153b44afbef2200885f379dc"
        smile.smile_version = "3.2.8"
        smile.smile_type = "thermostat"
        smile.smile_hostname = "smile98765"
        smile.smile_model = "Gateway"
        smile.smile_model_id = "smile_open_therm"
        smile.smile_name = "Adam"
        smile.connect.return_value = Version("3.2.8")
        all_data = _read_json(chosen_env, "all_data")
        smile.async_update.return_value = PlugwiseData(
            all_data["devices"], all_data["gateway"]
        )

        yield smile


@pytest.fixture
def mock_smile_anna() -> Generator[MagicMock]:
    """Create a Mock Anna environment for testing exceptions."""
    chosen_env = "anna_heatpump_heating"
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "015ae9ea3f964e668e490fa39da3870b"
        smile.heater_id = "1cbf783bb11e4a7c8a6843dee3a86927"
        smile.smile_version = "4.0.15"
        smile.smile_type = "thermostat"
        smile.smile_hostname = "smile98765"
        smile.smile_model = "Gateway"
        smile.smile_model_id = "smile_thermo"
        smile.smile_name = "Smile Anna"
        smile.connect.return_value = Version("4.0.15")
        all_data = _read_json(chosen_env, "all_data")
        smile.async_update.return_value = PlugwiseData(
            all_data["devices"], all_data["gateway"]
        )

        yield smile


@pytest.fixture
def mock_smile_anna_2() -> Generator[MagicMock]:
    """Create a 2nd Mock Anna environment for testing exceptions."""
    chosen_env = "m_anna_heatpump_cooling"
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "015ae9ea3f964e668e490fa39da3870b"
        smile.heater_id = "1cbf783bb11e4a7c8a6843dee3a86927"
        smile.smile_version = "4.0.15"
        smile.smile_type = "thermostat"
        smile.smile_hostname = "smile98765"
        smile.smile_model = "Gateway"
        smile.smile_model_id = "smile_thermo"
        smile.smile_name = "Smile Anna"
        smile.connect.return_value = Version("4.0.15")
        all_data = _read_json(chosen_env, "all_data")
        smile.async_update.return_value = PlugwiseData(
            all_data["devices"], all_data["gateway"]
        )

        yield smile


@pytest.fixture
def mock_smile_anna_3() -> Generator[MagicMock]:
    """Create a 3rd Mock Anna environment for testing exceptions."""
    chosen_env = "m_anna_heatpump_idle"
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "015ae9ea3f964e668e490fa39da3870b"
        smile.heater_id = "1cbf783bb11e4a7c8a6843dee3a86927"
        smile.smile_version = "4.0.15"
        smile.smile_type = "thermostat"
        smile.smile_hostname = "smile98765"
        smile.smile_model = "Gateway"
        smile.smile_model_id = "smile_thermo"
        smile.smile_name = "Smile Anna"
        smile.connect.return_value = Version("4.0.15")
        all_data = _read_json(chosen_env, "all_data")
        smile.async_update.return_value = PlugwiseData(
            all_data["devices"], all_data["gateway"]
        )

        yield smile


@pytest.fixture
def mock_smile_p1() -> Generator[MagicMock]:
    """Create a Mock P1 DSMR environment for testing exceptions."""
    chosen_env = "p1v4_442_single"
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "a455b61e52394b2db5081ce025a430f3"
        smile.heater_id = None
        smile.smile_version = "4.4.2"
        smile.smile_type = "power"
        smile.smile_hostname = "smile98765"
        smile.smile_model = "Gateway"
        smile.smile_model_id = "smile"
        smile.smile_name = "Smile P1"
        smile.connect.return_value = Version("4.4.2")
        all_data = _read_json(chosen_env, "all_data")
        smile.async_update.return_value = PlugwiseData(
            all_data["devices"], all_data["gateway"]
        )

        yield smile


@pytest.fixture
def mock_smile_p1_2() -> Generator[MagicMock]:
    """Create a Mock P1 3-phase DSMR environment for testing exceptions."""
    chosen_env = "p1v4_442_triple"
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "03e65b16e4b247a29ae0d75a78cb492e"
        smile.heater_id = None
        smile.smile_version = "4.4.2"
        smile.smile_type = "power"
        smile.smile_hostname = "smile98765"
        smile.smile_model = "Gateway"
        smile.smile_model_id = "smile"
        smile.smile_name = "Smile P1"
        smile.connect.return_value = Version("4.4.2")
        all_data = _read_json(chosen_env, "all_data")
        smile.async_update.return_value = PlugwiseData(
            all_data["devices"], all_data["gateway"]
        )

        yield smile


@pytest.fixture
def mock_smile_legacy_anna() -> Generator[MagicMock]:
    """Create a Mock legacy Anna environment for testing exceptions."""
    chosen_env = "legacy_anna"
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "0000aaaa0000aaaa0000aaaa0000aa00"
        smile.heater_id = "04e4cbfe7f4340f090f85ec3b9e6a950"
        smile.smile_version = "1.8.22"
        smile.smile_type = "thermostat"
        smile.smile_hostname = "smile98765"
        smile.smile_model = "Gateway"
        smile.smile_model_id = None
        smile.smile_name = "Smile Anna"
        smile.connect.return_value = Version("1.8.22")
        all_data = _read_json(chosen_env, "all_data")
        smile.async_update.return_value = PlugwiseData(
            all_data["devices"], all_data["gateway"]
        )

        yield smile


@pytest.fixture
def mock_stretch() -> Generator[MagicMock]:
    """Create a Mock Stretch environment for testing exceptions."""
    chosen_env = "stretch_v31"
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "259882df3c05415b99c2d962534ce820"
        smile.heater_id = None
        smile.smile_version = "3.1.11"
        smile.smile_type = "stretch"
        smile.smile_hostname = "stretch98765"
        smile.smile_model = "Gateway"
        smile.smile_model_id = None
        smile.smile_name = "Stretch"
        smile.connect.return_value = Version("3.1.11")
        all_data = _read_json(chosen_env, "all_data")
        smile.async_update.return_value = PlugwiseData(
            all_data["devices"], all_data["gateway"]
        )

        yield smile


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Plugwise integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
