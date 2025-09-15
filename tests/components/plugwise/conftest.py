"""Setup mocks for the Plugwise integration tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from munch import Munch
from packaging.version import Version
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


def build_smile(**attrs):
    """Build smile Munch from provided attributes."""
    smile = Munch()
    for k, v in attrs.items():
        setattr(smile, k, v)
    return smile


def _read_json(environment: str, call: str) -> dict[str, Any]:
    """Undecode the json data."""
    fixture = load_fixture(f"plugwise/{environment}/{call}.json")
    return json.loads(fixture)


@pytest.fixture
def cooling_present(request: pytest.FixtureRequest) -> str:
    """Pass the cooling_present boolean.

    Used with fixtures that require parametrization of the cooling capability.
    """
    return request.param


@pytest.fixture
def chosen_env(request: pytest.FixtureRequest) -> str:
    """Pass the chosen_env string.

    Used with fixtures that require parametrization of the user-data fixture.
    """
    return request.param


@pytest.fixture
def gateway_id(request: pytest.FixtureRequest) -> str:
    """Pass the gateway_id string.

    Used with fixtures that require parametrization of the gateway_id.
    """
    return request.param


@pytest.fixture
def heater_id(request: pytest.FixtureRequest) -> str:
    """Pass the heater_idstring.

    Used with fixtures that require parametrization of the heater_id.
    """
    return request.param


@pytest.fixture
def reboot(request: pytest.FixtureRequest) -> str:
    """Pass the reboot boolean.

    Used with fixtures that require parametrization of the reboot capability.
    """
    return request.param


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
    ) as api_mock:
        api = api_mock.return_value

        api.connect.return_value = Version("4.3.2")
        api.smile = build_smile(
            hostname="smile12345",
            model="Test Model",
            model_id="Test Model ID",
            name="Test Smile Name",
            version="4.3.2",
        )

        yield api


@pytest.fixture
def platforms() -> list[str]:
    """Fixture for platforms."""
    return []


@pytest.fixture
async def setup_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms,
) -> AsyncGenerator[None]:
    """Set up one or all platforms."""

    mock_config_entry.add_to_hass(hass)

    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_config_entry


@pytest.fixture
def mock_smile_adam() -> Generator[MagicMock]:
    """Create a Mock Adam environment for testing exceptions."""
    chosen_env = "m_adam_multiple_devices_per_zone"
    data = _read_json(chosen_env, "data")
    with (
        patch(
            "homeassistant.components.plugwise.coordinator.Smile", autospec=True
        ) as api_mock,
        patch(
            "homeassistant.components.plugwise.config_flow.Smile",
            new=api_mock,
        ),
    ):
        api = api_mock.return_value

        api.async_update.return_value = data
        api.cooling_present = False
        api.connect.return_value = Version("3.0.15")
        api.gateway_id = "fe799307f1624099878210aa0b9f1475"
        api.heater_id = "90986d591dcd426cae3ec3e8111ff730"
        api.reboot = True
        api.smile = build_smile(
            hostname="smile98765",
            model="Gateway",
            model_id="smile_open_therm",
            name="Adam",
            type="thermostat",
            version="3.0.15",
        )

        yield api


@pytest.fixture
def mock_smile_adam_heat_cool(
    chosen_env: str, cooling_present: bool
) -> Generator[MagicMock]:
    """Create a special base Mock Adam type for testing with different datasets."""
    data = _read_json(chosen_env, "data")
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as api_mock:
        api = api_mock.return_value

        api.async_update.return_value = data
        api.connect.return_value = Version("3.6.4")
        api.cooling_present = cooling_present
        api.gateway_id = "da224107914542988a88561b4452b0f6"
        api.heater_id = "056ee145a816487eaa69243c3280f8bf"
        api.reboot = True
        api.smile = build_smile(
            hostname="smile98765",
            model="Gateway",
            model_id="smile_open_therm",
            name="Adam",
            type="thermostat",
            version="3.6.4",
        )

        yield api


@pytest.fixture
def mock_smile_adam_jip() -> Generator[MagicMock]:
    """Create a Mock adam-jip type for testing exceptions."""
    chosen_env = "m_adam_jip"
    data = _read_json(chosen_env, "data")
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as api_mock:
        api = api_mock.return_value

        api.async_update.return_value = data
        api.connect.return_value = Version("3.2.8")
        api.cooling_present = False
        api.gateway_id = "b5c2386c6f6342669e50fe49dd05b188"
        api.heater_id = "e4684553153b44afbef2200885f379dc"
        api.reboot = True
        api.smile = build_smile(
            hostname="smile98765",
            model="Gateway",
            model_id="smile_open_therm",
            name="Adam",
            type="thermostat",
            version="3.2.8",
        )

        yield api


@pytest.fixture
def mock_smile_anna(chosen_env: str, cooling_present: bool) -> Generator[MagicMock]:
    """Create a Mock Anna type for testing."""
    data = _read_json(chosen_env, "data")
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as api_mock:
        api = api_mock.return_value

        api.async_update.return_value = data
        api.connect.return_value = Version("4.0.15")
        api.cooling_present = cooling_present
        api.gateway_id = "015ae9ea3f964e668e490fa39da3870b"
        api.heater_id = "1cbf783bb11e4a7c8a6843dee3a86927"
        api.reboot = True
        api.smile = build_smile(
            hostname="smile98765",
            model="Gateway",
            model_id="smile_thermo",
            name="Smile Anna",
            type="thermostat",
            version="4.0.15",
        )

        yield api


@pytest.fixture
def mock_smile_p1(chosen_env: str, gateway_id: str) -> Generator[MagicMock]:
    """Create a base Mock P1 type for testing with different datasets and gateway-ids."""
    data = _read_json(chosen_env, "data")
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as api_mock:
        api = api_mock.return_value

        api.async_update.return_value = data
        api.connect.return_value = Version("4.4.2")
        api.gateway_id = gateway_id
        api.heater_id = None
        api.reboot = True
        api.smile = build_smile(
            hostname="smile98765",
            model="Gateway",
            model_id="smile",
            name="Smile P1",
            type="power",
            version="4.4.2",
        )

        yield api


@pytest.fixture
def mock_smile_legacy_anna() -> Generator[MagicMock]:
    """Create a Mock legacy Anna environment for testing exceptions."""
    chosen_env = "legacy_anna"
    data = _read_json(chosen_env, "data")
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as api_mock:
        api = api_mock.return_value

        api.async_update.return_value = data
        api.connect.return_value = Version("1.8.22")
        api.gateway_id = "0000aaaa0000aaaa0000aaaa0000aa00"
        api.heater_id = "04e4cbfe7f4340f090f85ec3b9e6a950"
        api.reboot = False
        api.smile = build_smile(
            hostname="smile98765",
            model="Gateway",
            model_id=None,
            name="Smile Anna",
            type="thermostat",
            version="1.8.22",
        )

        yield api


@pytest.fixture
def mock_stretch() -> Generator[MagicMock]:
    """Create a Mock Stretch environment for testing exceptions."""
    chosen_env = "stretch_v31"
    data = _read_json(chosen_env, "data")
    with patch(
        "homeassistant.components.plugwise.coordinator.Smile", autospec=True
    ) as api_mock:
        api = api_mock.return_value

        api.async_update.return_value = data
        api.connect.return_value = Version("3.1.11")
        api.gateway_id = "259882df3c05415b99c2d962534ce820"
        api.heater_id = None
        api.reboot = False
        api.smile = build_smile(
            hostname="stretch98765",
            model="Gateway",
            model_id=None,
            name="Stretch",
            type="stretch",
            version="3.1.11",
        )

        yield api


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Plugwise integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
