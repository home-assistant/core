"""Tests for the diagnostics data provided by the Sunricher DALI integration."""

import json
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sunricher_dali.diagnostics import ALLOWED_ENTRY_KEYS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import DEVICE_DATA, GATEWAY_SERIAL, _create_mock_device

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

EXPECTED_DEVICE_KEYS = frozenset(
    {
        "dev_id",
        "unique_id",
        "name",
        "dev_type",
        "channel",
        "address",
        "status",
        "dev_sn",
        "area_name",
        "area_id",
        "model",
    }
)

EXPECTED_SCENE_KEYS = frozenset(
    {
        "scene_id",
        "name",
        "channel",
        "area_id",
        "unique_id",
        "device_unique_ids",
    }
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Keep init_integration setup minimal."""
    return []


@pytest.fixture
def mock_devices() -> list[MagicMock]:
    """Return a unique device list for a clean snapshot."""
    return [_create_mock_device(data) for data in DEVICE_DATA]


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics output matches the stored snapshot."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )


async def test_diagnostics_structure(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test top-level structure."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert set(result.keys()) == {"entry_data", "devices", "scenes"}
    assert isinstance(result["devices"], list)
    assert isinstance(result["scenes"], list)
    assert len(result["devices"]) > 0
    assert len(result["scenes"]) > 0


async def test_diagnostics_redacts_entry_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test credentials and host are redacted in entry_data."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    entry_data = result["entry_data"]
    assert entry_data["host"] == "**REDACTED**"
    assert entry_data["username"] == "**REDACTED**"
    assert entry_data["password"] == "**REDACTED**"
    assert entry_data["serial_number"] == "**REDACTED**"


async def test_diagnostics_entry_data_is_whitelisted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test entry_data only contains whitelisted keys."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert set(result["entry_data"]).issubset(ALLOWED_ENTRY_KEYS)


async def test_diagnostics_device_keys_are_exact(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test each device entry exposes exactly the whitelisted keys."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    for device in result["devices"]:
        assert set(device.keys()) == EXPECTED_DEVICE_KEYS


async def test_diagnostics_scene_keys_are_exact(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test each scene entry exposes exactly the whitelisted keys."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    for scene in result["scenes"]:
        assert set(scene.keys()) == EXPECTED_SCENE_KEYS


async def test_diagnostics_redacts_device_dev_sn(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test dev_sn is redacted in each device entry."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    for device in result["devices"]:
        assert device["dev_sn"] == "**REDACTED**"


async def test_diagnostics_preserves_unique_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test dev_id and unique_id keep their structural prefix."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    for device in result["devices"]:
        assert device["dev_id"] == device["unique_id"]
        assert "**REDACTED**" in device["dev_id"]
        assert device["dev_id"] != "**REDACTED**"


async def test_diagnostics_strips_gw_sn(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test gateway serial number never appears anywhere in the output."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    assert GATEWAY_SERIAL not in json.dumps(result)


async def test_diagnostics_empty_runtime(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test diagnostics handles a gateway with zero devices and zero scenes."""
    mock_gateway.discover_devices.return_value = []
    mock_gateway.discover_scenes.return_value = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["devices"] == []
    assert result["scenes"] == []
    assert "entry_data" in result
