"""Fixtures for Local vision tests."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
    setup_test_component_platform,
)

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.local_vision.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ENTITY_ID, CONF_REGION, Platform
from homeassistant.core import HomeAssistant

from . import CAMERA, REGION, TEST_DOMAIN, FakeCamera


@pytest.fixture(autouse=True)
def config_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Keep taught frames out of the test config folder."""
    hass.config.config_dir = str(tmp_path)
    return tmp_path


@pytest.fixture
async def camera(hass: HomeAssistant) -> FakeCamera:
    """Set up a camera entity on its own device."""
    fake = FakeCamera()

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.CAMERA])
        return True

    mock_integration(hass, MockModule(TEST_DOMAIN, async_setup_entry=async_setup_entry))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", Mock())
    setup_test_component_platform(hass, CAMERA_DOMAIN, [fake], from_config_entry=True)
    camera_entry = MockConfigEntry(domain=TEST_DOMAIN)
    camera_entry.add_to_hass(hass)
    with mock_config_flow(TEST_DOMAIN, ConfigFlow):
        assert await hass.config_entries.async_setup(camera_entry.entry_id)
        await hass.async_block_till_done()
    return fake


@pytest.fixture
def device_class() -> str:
    """Return the device class of the configured entry."""
    return "occupancy"


@pytest.fixture
def mock_config_entry(device_class: str) -> MockConfigEntry:
    """Return a configured entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Garage",
        entry_id="01JLOCALVISION0000000000000",
        options={
            CONF_ENTITY_ID: CAMERA,
            CONF_REGION: REGION,
            CONF_DEVICE_CLASS: device_class,
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip setting up entries created by the config flow."""
    with patch(
        "homeassistant.components.local_vision.async_setup_entry", return_value=True
    ) as mock:
        yield mock
