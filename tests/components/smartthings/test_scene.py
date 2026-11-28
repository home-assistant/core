"""Test for the SmartThings scene platform."""

from unittest.mock import AsyncMock

from pysmartthings import SmartThingsForbiddenError, SmartThingsQuotaExceededError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SceneService
from homeassistant.components.smartthings.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_smartthings_entities


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SCENE)


async def test_activate_scene(
    hass: HomeAssistant,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test activating a scene."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SCENE_DOMAIN,
        SceneService.TURN_ON,
        {TargetKey.ENTITY_ID: "scene.away"},
        blocking=True,
    )

    mock_smartthings.execute_scene.assert_called_once_with(
        "743b0f37-89b8-476c-aedf-eea8ad8cd29d"
    )


async def test_activate_scene_quota_exceeded(
    hass: HomeAssistant,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a quota exceeded error when activating a scene is translated."""
    await setup_integration(hass, mock_config_entry)
    mock_smartthings.execute_scene.side_effect = SmartThingsQuotaExceededError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SCENE_DOMAIN,
            SceneService.TURN_ON,
            {TargetKey.ENTITY_ID: "scene.away"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "quota_exceeded"


async def test_activate_scene_forbidden(
    hass: HomeAssistant,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a forbidden scene activation reports the entitlement error and starts reauth."""
    await setup_integration(hass, mock_config_entry)
    mock_smartthings.execute_scene.side_effect = SmartThingsForbiddenError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SCENE_DOMAIN,
            SceneService.TURN_ON,
            {TargetKey.ENTITY_ID: "scene.away"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "entitlement_required"
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
