"""Test the Matter diagnostics platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

from matter_server.common.helpers.util import dataclass_from_dict
from matter_server.common.models import ServerDiagnostics
import pytest

from homeassistant.components.matter.const import DOMAIN
from homeassistant.components.matter.diagnostics import redact_matter_attributes
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import setup_integration_with_node_fixture

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


@pytest.fixture(name="config_entry_diagnostics")
def config_entry_diagnostics_fixture() -> dict[str, Any]:
    """Fixture for config entry diagnostics."""
    return json.loads(load_fixture("config_entry_diagnostics.json", DOMAIN))


@pytest.fixture(name="config_entry_diagnostics_redacted")
def config_entry_diagnostics_redacted_fixture() -> dict[str, Any]:
    """Fixture for redacted config entry diagnostics."""
    return json.loads(load_fixture("config_entry_diagnostics_redacted.json", DOMAIN))


@pytest.fixture(name="device_diagnostics")
def device_diagnostics_fixture() -> dict[str, Any]:
    """Fixture for device diagnostics."""
    return json.loads(load_fixture("nodes/device_diagnostics.json", DOMAIN))


async def test_matter_attribute_redact(device_diagnostics: dict[str, Any]) -> None:
    """Test the matter attribute redact helper."""
    assert device_diagnostics["attributes"]["0/40/6"] == "XX"

    redacted_device_diagnostics = redact_matter_attributes(device_diagnostics)

    # Check that the correct attribute value is redacted.
    assert redacted_device_diagnostics["attributes"]["0/40/6"] == "**REDACTED**"

    # Check that the other attribute values are not redacted.
    redacted_device_diagnostics["attributes"]["0/40/6"] = "XX"
    assert redacted_device_diagnostics == device_diagnostics


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    matter_client: MagicMock,
    integration: MockConfigEntry,
    config_entry_diagnostics: dict[str, Any],
    config_entry_diagnostics_redacted: dict[str, Any],
) -> None:
    """Test the config entry level diagnostics."""
    matter_client.get_diagnostics.return_value = dataclass_from_dict(
        ServerDiagnostics, config_entry_diagnostics
    )

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, integration)

    assert diagnostics == config_entry_diagnostics_redacted


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
    config_entry_diagnostics: dict[str, Any],
    device_diagnostics: dict[str, Any],
) -> None:
    """Test the device diagnostics."""
    await setup_integration_with_node_fixture(hass, "device_diagnostics", matter_client)
    system_info_dict = config_entry_diagnostics["info"]
    device_diagnostics_redacted = {
        "server_info": system_info_dict,
        "node": redact_matter_attributes(device_diagnostics),
    }
    server_diagnostics_response = {
        "info": system_info_dict,
        "nodes": [device_diagnostics],
        "events": [],
    }
    server_diagnostics = dataclass_from_dict(
        ServerDiagnostics, server_diagnostics_response
    )
    matter_client.get_diagnostics.return_value = server_diagnostics
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    device = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)[
        0
    ]
    assert device

    diagnostics = await get_diagnostics_for_device(
        hass, hass_client, config_entry, device
    )
    assert diagnostics == device_diagnostics_redacted
