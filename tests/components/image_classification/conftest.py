"""Fixtures for Image classification tests."""

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

from homeassistant.components.ai_task import DOMAIN as AI_TASK_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.image_classification.const import (
    CONF_AI_TASK_ENTITY_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ENTITY_ID, CONF_REGION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import CAMERA, CLASSIFIER, REGION, TEST_DOMAIN, FakeCamera, FakeClassifier


@pytest.fixture(autouse=True)
def config_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Keep taught frames out of the test config folder."""
    hass.config.config_dir = str(tmp_path)
    return tmp_path


@pytest.fixture
def classifier() -> FakeClassifier:
    """Return the AI Task entity set up with the camera."""
    return FakeClassifier()


@pytest.fixture
async def camera(hass: HomeAssistant, classifier: FakeClassifier) -> FakeCamera:
    """Set up a camera on its own device and an AI Task entity."""
    fake = FakeCamera()

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(
            entry, [Platform.AI_TASK, Platform.CAMERA]
        )
        return True

    # Conversation, a dependency of AI Task, needs the core integration.
    assert await async_setup_component(hass, "homeassistant", {})
    mock_integration(hass, MockModule(TEST_DOMAIN, async_setup_entry=async_setup_entry))
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", Mock())
    setup_test_component_platform(hass, CAMERA_DOMAIN, [fake], from_config_entry=True)
    setup_test_component_platform(
        hass, AI_TASK_DOMAIN, [classifier], from_config_entry=True
    )
    camera_entry = MockConfigEntry(domain=TEST_DOMAIN)
    camera_entry.add_to_hass(hass)
    with mock_config_flow(TEST_DOMAIN, ConfigFlow):
        assert await hass.config_entries.async_setup(camera_entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get(CLASSIFIER)
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
        entry_id="01JIMAGECLASSIFICATION00000",
        options={
            CONF_ENTITY_ID: CAMERA,
            CONF_REGION: REGION,
            CONF_DEVICE_CLASS: device_class,
            CONF_AI_TASK_ENTITY_ID: CLASSIFIER,
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip setting up entries created by the config flow."""
    with patch(
        "homeassistant.components.image_classification.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock
