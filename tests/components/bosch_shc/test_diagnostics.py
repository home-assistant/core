"""Tests for Bosch SHC diagnostics."""

from unittest.mock import MagicMock

import pytest

from homeassistant.core import HomeAssistant

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics_full(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Full diagnostics dump: session loaded, one device, fields + redaction."""
    # Build a service mock so _device_dump includes a service entry.
    svc = MagicMock()
    svc.id = "PowerMeter"
    svc.state = {"energyWh": 123}

    dev = make_device("device-1", "Living Room Switch", device_model="PSM")
    dev.device_services = [svc]

    # The session mock is what mock_setup_dependencies yields.
    session = mock_setup_dependencies
    session.devices = [dev]

    # Add the attributes that diagnostics.py reads off session.information
    # (the conftest mock_session.information only specs unique_id/name/version).
    info = session.information
    info.updateState = MagicMock()
    info.updateState.name = "NO_UPDATE_AVAILABLE"
    info.macAddress = "AA:BB:CC:DD:EE:FF"
    info.shcIpAddress = "192.168.1.50"

    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    # ── top-level structure ──────────────────────────────────────────────────
    assert "entry" in result
    assert "shc" in result
    assert "device_count" in result
    assert "devices" in result

    # ── config entry block ───────────────────────────────────────────────────
    entry_block = result["entry"]
    assert entry_block["title"] == "shc012345"
    entry_data = entry_block["data"]

    # host, ssl_certificate, ssl_key, token, hostname are all in TO_REDACT
    assert entry_data["host"] == "**REDACTED**"
    assert entry_data["ssl_certificate"] == "**REDACTED**"
    assert entry_data["ssl_key"] == "**REDACTED**"
    assert entry_data["token"] == "**REDACTED**"
    assert entry_data["hostname"] == "**REDACTED**"

    # options block is present (empty for this entry)
    assert entry_block["options"] == {}

    # ── SHC controller block ─────────────────────────────────────────────────
    shc_block = result["shc"]
    assert shc_block["version"] == "10.0.0"
    assert shc_block["update_state"] == "NO_UPDATE_AVAILABLE"
    # macAddress and ip are in TO_REDACT
    assert shc_block["macAddress"] == "**REDACTED**"
    assert shc_block["ip"] == "**REDACTED**"

    # ── devices ──────────────────────────────────────────────────────────────
    assert result["device_count"] == 1
    devices = result["devices"]
    assert len(devices) == 1

    device = devices[0]
    assert device["id"] == "device-1"
    assert device["name"] == "Living Room Switch"
    assert device["device_model"] == "PSM"
    assert device["manufacturer"] == "BOSCH"
    assert device["room_id"] == "room-1"

    # root_device_id and serial are in TO_REDACT
    assert device["root_device_id"] == "**REDACTED**"
    assert device["serial"] == "**REDACTED**"

    # services list
    services = device["services"]
    assert len(services) == 1
    assert services[0]["id"] == "PowerMeter"
    assert services[0]["state"] == {"energyWh": 123}


async def test_diagnostics_no_session(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When runtime_data.session is None the dump still returns an entry block."""
    # Force session to None so the early-return branch is hit.
    mock_setup_dependencies.session = None  # type: ignore[attr-defined]

    # Wrap runtime_data so entry.runtime_data.session resolves to None.
    runtime = MagicMock()
    runtime.session = None

    await setup_integration(hass, mock_config_entry)
    # Inject the None-session runtime_data after setup (session was already used
    # for async_init/start_polling, so setup succeeded; we patch runtime_data now).
    mock_config_entry.runtime_data = runtime

    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert "entry" in result
    assert result["session"] == "not loaded"
    assert "shc" not in result
    assert "devices" not in result


async def test_diagnostics_empty_devices(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Session with zero devices produces device_count=0 and empty list."""
    session = mock_setup_dependencies
    session.devices = []

    info = session.information
    info.updateState = MagicMock()
    info.updateState.name = "UPDATE_AVAILABLE"
    info.macAddress = "11:22:33:44:55:66"
    info.shcIpAddress = "10.0.0.1"

    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert result["device_count"] == 0
    assert result["devices"] == []
    assert result["shc"]["update_state"] == "UPDATE_AVAILABLE"


async def test_diagnostics_multiple_devices(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Multiple devices all appear in the dump with correct device_count."""
    session = mock_setup_dependencies
    session.devices = [
        make_device("dev-a", "Device A"),
        make_device("dev-b", "Device B"),
        make_device("dev-c", "Device C"),
    ]

    info = session.information
    info.updateState = MagicMock()
    info.updateState.name = "NO_UPDATE_AVAILABLE"
    info.macAddress = "AA:BB:CC:00:00:01"
    info.shcIpAddress = "192.168.2.10"

    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert result["device_count"] == 3
    assert len(result["devices"]) == 3
    names = {d["name"] for d in result["devices"]}
    assert names == {"Device A", "Device B", "Device C"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("host", "**REDACTED**"),
        ("ssl_certificate", "**REDACTED**"),
        ("ssl_key", "**REDACTED**"),
        ("token", "**REDACTED**"),
        ("hostname", "**REDACTED**"),
    ],
)
async def test_diagnostics_redacted_config_entry_fields(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    field: str,
    value: str,
) -> None:
    """Each credential/network field in the config entry data is redacted."""
    session = mock_setup_dependencies
    session.devices = []

    info = session.information
    info.updateState = MagicMock()
    info.updateState.name = "NO_UPDATE_AVAILABLE"
    info.macAddress = "AA:BB:CC:DD:EE:FF"
    info.shcIpAddress = "192.168.1.1"

    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert result["entry"]["data"][field] == value
