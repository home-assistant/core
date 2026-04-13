"""Tests for the diagnostics data provided by the Sunricher DALI integration."""

import json
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sunricher_dali.diagnostics import (
    ALLOWED_ENTRY_KEYS,
    _serialize_device,
    _serialize_scene,
    _strip_gw_sn,
)
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
    """Override platforms used during init_integration to keep setup minimal."""
    return []


@pytest.fixture
def mock_devices() -> list[MagicMock]:
    """Override the shared fixture with a unique, duplicate-free device list.

    The shared conftest fixture intentionally appends a duplicate device to
    exercise duplicate-handling in other tests. For the diagnostics snapshot,
    a clean unique list keeps the output easier to reason about.
    """
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
    """Diagnostics output must contain exactly entry_data, devices, scenes."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert set(result.keys()) == {"entry_data", "devices", "scenes"}
    assert "gateway" not in result
    assert isinstance(result["devices"], list)
    assert isinstance(result["scenes"], list)
    assert len(result["devices"]) > 0
    assert len(result["scenes"]) > 0


async def test_diagnostics_redacts_entry_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Credentials and host must be redacted in entry_data."""
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
    """entry_data must only contain keys from ALLOWED_ENTRY_KEYS.

    This turns the key whitelist into a mechanical contract: any new
    field added to entry.data must be explicitly opted in.
    """
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert set(result["entry_data"]).issubset(ALLOWED_ENTRY_KEYS)


async def test_diagnostics_redacts_device_dev_sn(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """dev_sn must be redacted in each device entry."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    for device in result["devices"]:
        assert device["dev_sn"] == "**REDACTED**"


async def test_diagnostics_preserves_unique_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """dev_id and unique_id must keep their structural prefix for traceability.

    The gw_sn suffix is stripped by the post-processing redactor, but the
    dev_type/channel/address prefix is preserved so developers can still
    correlate diagnostics entries with HA entity registry records.
    """
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    for device in result["devices"]:
        assert device["dev_id"] is not None
        assert device["unique_id"] is not None
        assert device["dev_id"] == device["unique_id"]
        assert "**REDACTED**" in device["dev_id"]
        assert device["dev_id"] != "**REDACTED**"


async def test_diagnostics_strips_gw_sn(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """The gateway serial number must never appear anywhere in the output.

    This is a hard anti-leak guarantee: even though dev_id / unique_id are
    preserved for traceability, their gw_sn suffix must be stripped by the
    post-processing redactor before the payload is returned.
    """
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    assert GATEWAY_SERIAL not in json.dumps(result)


async def test_diagnostics_no_private_attrs(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Serialized devices and scenes must not expose private attributes."""
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    for device in result["devices"]:
        assert not any(key.startswith("_") for key in device)
    for scene in result["scenes"]:
        assert not any(key.startswith("_") for key in scene)
        assert "gw_sn_obj" not in scene
        assert "property" not in scene


def test_serialized_device_keys_are_exact(mock_devices: list[MagicMock]) -> None:
    """The device whitelist must be exactly EXPECTED_DEVICE_KEYS.

    Any addition or removal must be deliberate and update both
    _serialize_device and EXPECTED_DEVICE_KEYS together.
    """
    serialized = _serialize_device(mock_devices[0])
    assert set(serialized.keys()) == EXPECTED_DEVICE_KEYS


def test_serialized_scene_keys_are_exact(mock_scenes: list[MagicMock]) -> None:
    """The scene whitelist must be exactly EXPECTED_SCENE_KEYS."""
    serialized = _serialize_scene(mock_scenes[0])
    assert set(serialized.keys()) == EXPECTED_SCENE_KEYS


def test_strip_gw_sn_noop_on_empty_serial() -> None:
    """_strip_gw_sn must return the input unchanged when gw_sn is empty."""
    payload = {"devices": [{"dev_id": "0101000002ABC123"}]}
    assert _strip_gw_sn(payload, "") is payload


async def test_diagnostics_empty_runtime(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Diagnostics handles a gateway with zero devices and zero scenes."""
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
