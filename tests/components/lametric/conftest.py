"""Fixtures for LaMetric integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from demetriek import CloudDevice, Device
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.lametric.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture, load_json_array_fixture


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential("client", "secret"), "credentials"
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My LaMetric",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.2",
            CONF_API_KEY: "mock-from-fixture",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        },
        unique_id="SA110405124500W00BS9",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.lametric.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_lametric_cloud() -> Generator[MagicMock]:
    """Return a mocked LaMetric Cloud client."""
    with patch(
        "homeassistant.components.lametric.config_flow.LaMetricCloud", autospec=True
    ) as lametric_mock:
        lametric = lametric_mock.return_value
        lametric.devices.return_value = [
            CloudDevice.from_dict(cloud_device)
            for cloud_device in load_json_array_fixture("cloud_devices.json", DOMAIN)
        ]
        yield lametric


@pytest.fixture
def device_fixture() -> str:
    """Return the device fixture for a specific device."""
    return "device"


@pytest.fixture
def mock_lametric(device_fixture: str) -> Generator[MagicMock]:
    """Return a mocked LaMetric TIME client."""
    with (
        patch(
            "homeassistant.components.lametric.coordinator.LaMetricDevice",
            autospec=True,
        ) as lametric_mock,
        patch(
            "homeassistant.components.lametric.config_flow.LaMetricDevice",
            new=lametric_mock,
        ),
    ):
        lametric = lametric_mock.return_value
        lametric.api_key = "mock-api-key"
        lametric.host = "127.0.0.1"
        lametric.device.return_value = Device.from_json(
            load_fixture(f"{device_fixture}.json", DOMAIN)
        )
        yield lametric


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_lametric: MagicMock
) -> MockConfigEntry:
    """Set up the LaMetric integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
