"""The test for the Yale Smart ALarm lock platform."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import Mock

import pytest
from syrupy.assertion import SnapshotAssertion
from yalesmartalarmclient.lock import YaleDoorManAPI

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.LOCK]],
)
async def test_lock(
    hass: HomeAssistant,
    load_config_entry: tuple[MockConfigEntry, Mock],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Yale Smart Alarm lock."""
    entry = load_config_entry[0]
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.LOCK]],
)
async def test_lock_service_calls(
    hass: HomeAssistant,
    load_json: dict[str, Any],
    load_config_entry: tuple[MockConfigEntry, Mock],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Yale Smart Alarm lock."""

    client = load_config_entry[1]

    data = deepcopy(load_json)
    data["data"] = data.pop("DEVICES")

    client.auth.get_authenticated = Mock(return_value=data)
    client.lock_api = YaleDoorManAPI(client.auth)
