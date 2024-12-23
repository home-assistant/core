"""Fixtures for JVC Projector integration."""

from collections.abc import Generator
import logging
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.jvc_projector.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from . import MOCK_HOST, MOCK_MAC, MOCK_MODEL, MOCK_PASSWORD, MOCK_PORT

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_device")
def fixture_mock_device(
    request: pytest.FixtureRequest,
) -> Generator[MagicMock]:
    """Return a mocked JVC Projector device."""
    target = "homeassistant.components.jvc_projector.JvcProjector"
    if hasattr(request, "param"):
        target = request.param

    with patch(target, autospec=True) as mock:
        device = mock.return_value
        device.host = MOCK_HOST
        device.port = MOCK_PORT
        device.mac = MOCK_MAC
        device.model = MOCK_MODEL
        device.get_state.return_value = {
            "power": "standby",
            "input": "hdmi1",
            "source": "signal",
            "picture_mode": "natural",
            "low_latency": "off",
            "installation_mode": "mode1",
            "eshift": "on",
            "laser_dimming": "auto1",
            "laser_value": "100",
            "laser_power": "high",
            "laser_time": "1000",
            "hdr_content_type": "sdr",
            "anamorphic": "off",
            "hdr": "none",
            "hdmi_input_level": "enhanced",
            "hdmi_color_space": "rgb",
            "color_profile": "bt2020(wide)",
            "graphics_mode": "standard",
            "color_space": "rgb",
            "motion_enhance": "low",
            "clear_motion_drive": "low",
            "hdr_processing": "1",
        }
        yield device


@pytest.fixture(name="mock_config_entry")
def fixture_mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_MAC,
        version=1,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )


@pytest.fixture(name="mock_integration")
async def fixture_mock_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Return a mock ConfigEntry setup for the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture(autouse=True)
def configure_logging():
    """Configure logging for tests."""
    logging.getLogger().handlers = [logging.NullHandler()]
