"""Fixtures for JVC Projector integration."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from jvcprojector import command as cmd
import pytest

from homeassistant.components.jvc_projector.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from . import MOCK_HOST, MOCK_MAC, MOCK_MODEL, MOCK_PASSWORD, MOCK_PORT

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_device")
def fixture_mock_device(
    request: pytest.FixtureRequest,
) -> Generator[MagicMock]:
    """Return a mocked JVC Projector device."""
    target = "homeassistant.components.jvc_projector.JvcProjector"
    fixture: dict[str, str] = {
        "mac": MOCK_MAC,
        "power": "standby",
        "input": "hdmi-1",
    }

    if hasattr(request, "param"):
        target = request.param.get("target", target)
        fixture = request.param.get("get", fixture)

    async def device_get(command) -> str:
        if command is cmd.MacAddress:
            return fixture["mac"]
        if command is cmd.Power:
            return fixture["power"]
        if command is cmd.Input:
            return fixture["input"]
        raise ValueError(f"Fixture failure; unexpected command {command}")

    with patch(target, autospec=True) as mock:
        device = mock.return_value
        device.host = MOCK_HOST
        device.port = MOCK_PORT
        device.model = MOCK_MODEL
        device.get.side_effect = device_get
        yield device


@pytest.fixture(name="mock_config_entry")
def fixture_mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(MOCK_MAC),
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
