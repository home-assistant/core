"""Tests for the SmartyPlants binary sensor platform."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.smartyplants.const import DOMAIN
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_added_entry, setup_integration

ONLINE = "binary_sensor.monstera_connectivity"
ATTENTION = "binary_sensor.monstera_needs_attention"


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test every binary sensor created from the first poll."""
    with patch(
        "homeassistant.components.smartyplants.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("is_online", "expected"),
    [
        pytest.param(True, STATE_ON, id="online"),
        pytest.param(False, STATE_OFF, id="offline"),
    ],
)
@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_connectivity_follows_the_backend(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sensor_payloads: list[dict[str, Any]],
    is_online: bool,
    expected: str,
) -> None:
    """Test connectivity reports what the backend says, as it says it."""
    sensor_payloads[0]["isOnline"] = is_online

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ONLINE).state == expected


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_connectivity_survives_going_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sensor_payloads: list[dict[str, Any]],
) -> None:
    """Test connectivity still answers once the sensor goes offline."""
    sensor_payloads[0]["isOnline"] = False

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ONLINE).state != STATE_UNAVAILABLE
    # Health is derived from readings, so it goes with the rest of them.
    assert hass.states.get(ATTENTION).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("is_healthy", "expected"),
    [
        pytest.param(True, STATE_OFF, id="healthy"),
        pytest.param(False, STATE_ON, id="unhealthy"),
        pytest.param(None, STATE_UNKNOWN, id="not_scored"),
    ],
)
@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_needs_attention(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sensor_payloads: list[dict[str, Any]],
    is_healthy: bool | None,
    expected: str,
) -> None:
    """Test the health flag is reported, and withheld when unscored."""
    sensor_payloads[0]["health"]["isHealthy"] = is_healthy

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ATTENTION).state == expected


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_entry_from_custom_integration_is_adopted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the custom integration's entity id is reused, not replaced."""
    mock_config_entry.add_to_hass(hass)
    existing = entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        "sensor-1_online",
        config_entry=mock_config_entry,
        suggested_object_id="monstera_online",
    )
    assert existing.entity_id == "binary_sensor.monstera_online"

    await setup_added_entry(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.monstera_online") is not None
    assert hass.states.get(ONLINE) is None
