"""Fixtures for JVC Projector integration."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from jvcprojector import Command, JvcProjectorTimeoutError, command as cmd
import pytest

from homeassistant.components.jvc_projector.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from . import MOCK_HOST, MOCK_MAC, MOCK_MODEL, MOCK_PASSWORD, MOCK_PORT

from tests.common import MockConfigEntry

FIXTURES: dict[str, dict[type[Command], str | type[Exception]]] = {
    "standby": {
        cmd.MacAddress: MOCK_MAC,
        cmd.ModelName: MOCK_MODEL,
        cmd.Power: "standby",
        cmd.Input: "hdmi1",
        cmd.Signal: "none",
        cmd.LightTime: "100",
        cmd.Source: JvcProjectorTimeoutError,
        cmd.Hdr: JvcProjectorTimeoutError,
        cmd.HdrProcessing: JvcProjectorTimeoutError,
        cmd.EShift: JvcProjectorTimeoutError,
    },
    "on": {
        cmd.MacAddress: MOCK_MAC,
        cmd.ModelName: MOCK_MODEL,
        cmd.Power: "on",
        cmd.Input: "hdmi1",
        cmd.Signal: "signal",
        cmd.LightTime: "100",
        cmd.Source: "4k",
        cmd.Hdr: "hdr",
        cmd.HdrProcessing: "static",
        cmd.EShift: "on",
    },
}

CAPABILITIES = {
    cmd.Power.name: {
        "name": cmd.Power.name,
        "parameter": {"read": {"0": "standby", "1": "on"}},
    },
    cmd.Input.name: {
        "name": cmd.Input.name,
        "parameter": {"read": {"6": "hdmi1", "7": "hdmi2"}},
    },
    cmd.Signal.name: {
        "name": cmd.Signal.name,
        "parameter": {"read": {"0": "none", "1": "signal"}},
    },
    cmd.Source.name: {
        "name": cmd.Source.name,
        "parameter": {"read": {"0": "4k"}},
    },
    cmd.Hdr.name: {
        "name": cmd.Hdr.name,
        "parameter": {"read": {"0": "sdr", "1": "hdr"}},
    },
    cmd.HdrProcessing.name: {
        "name": cmd.HdrProcessing.name,
        "parameter": {"read": {"0": "hdr", "1": "static"}},
    },
    cmd.LightTime.name: {
        "name": cmd.LightTime.name,
        "parameter": "empty",
    },
    cmd.EShift.name: {
        "name": cmd.EShift.name,
        "parameter": {"read": {"0": "off", "1": "on"}},
    },
}


@pytest.fixture(name="mock_device")
def fixture_mock_device(
    request: pytest.FixtureRequest,
) -> Generator[MagicMock]:
    """Return a mocked JVC Projector device."""
    target = "homeassistant.components.jvc_projector.JvcProjector"
    fixture = FIXTURES["on"].copy()

    if hasattr(request, "param"):
        target = request.param.get("target", target)
        if "fixture" in request.param:
            if isinstance(request.param["fixture"], str):
                fixture = FIXTURES[request.param["fixture"]].copy()
            else:
                fixture = request.param["fixture"].copy()

        if "fixture_override" in request.param:
            fixture.update(request.param["fixture_override"])

    async def device_get(command) -> str:
        if command in fixture:
            value = fixture[command]
            if isinstance(value, type) and issubclass(value, Exception):
                raise value
            return value
        raise ValueError(f"Test fixture failure; unexpected command {command}")

    with patch(target, autospec=True) as mock:
        device = mock.return_value
        device.ip = MOCK_HOST
        device.host = MOCK_HOST
        device.port = MOCK_PORT
        device.mac = MOCK_MAC
        device.model = MOCK_MODEL
        device.get.side_effect = device_get
        device.capabilities.return_value = CAPABILITIES
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
    with (
        patch("homeassistant.components.jvc_projector.coordinator.TIMEOUT_RETRIES", 2),
        patch("homeassistant.components.jvc_projector.coordinator.TIMEOUT_SLEEP", 0.1),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        return mock_config_entry
