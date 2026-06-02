"""Tests for the Overkiz scene platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import humps
from pyoverkiz.models import Scenario
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MockOverkizClient, SetupOverkizIntegration

from tests.common import load_json_array_fixture, snapshot_platform

SCENARIO_FIXTURES = [
    "scenarios/cozytouch.json",
    "scenarios/tahoma_switch.json",
]


def load_scenarios_fixture(fixture: str) -> list[Scenario]:
    """Load scenario fixture and return Scenario objects."""
    data = load_json_array_fixture(fixture, DOMAIN)
    return [Scenario(**humps.decamelize(s)) for s in data]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to scene only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.SCENE]):
        yield


@pytest.mark.parametrize("fixture", SCENARIO_FIXTURES)
async def test_scene_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    mock_client: MockOverkizClient,
    snapshot: SnapshotAssertion,
    fixture: str,
) -> None:
    """Test scene entities via snapshot for each fixture."""
    scenarios = load_scenarios_fixture(fixture)
    mock_client.get_scenarios = AsyncMock(return_value=scenarios)

    config_entry = await setup_overkiz_integration()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_scene_activate(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test activating a scene calls execute_scenario with the correct OID."""
    scenarios = load_scenarios_fixture("scenarios/tahoma_switch.json")
    mock_client.get_scenarios = AsyncMock(return_value=scenarios)
    mock_client.execute_scenario = AsyncMock(return_value="exec-1")

    await setup_overkiz_integration()

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "scene.i_m_arriving"},
        blocking=True,
    )

    mock_client.execute_scenario.assert_awaited_once_with(
        "d1b689e1-4087-473d-b726-d3b24770856f"
    )


async def test_scene_activate_multiple(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test activating different scenes uses the correct OID for each."""
    scenarios = load_scenarios_fixture("scenarios/cozytouch.json")
    mock_client.get_scenarios = AsyncMock(return_value=scenarios)
    mock_client.execute_scenario = AsyncMock(return_value="exec-1")

    await setup_overkiz_integration()

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "scene.label_1"},
        blocking=True,
    )

    mock_client.execute_scenario.assert_awaited_once_with(
        "0a0589bb-9471-4667-a2a9-4602beb2a2e8"
    )

    mock_client.execute_scenario.reset_mock()

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "scene.label_2"},
        blocking=True,
    )

    mock_client.execute_scenario.assert_awaited_once_with(
        "50d39fc3-9368-49c9-bcbf-c74f3ce1678a"
    )


async def test_no_scenes_when_empty(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test no scene entities are created when there are no scenarios."""
    await setup_overkiz_integration()

    states = hass.states.async_entity_ids(SCENE_DOMAIN)
    assert len(states) == 0
