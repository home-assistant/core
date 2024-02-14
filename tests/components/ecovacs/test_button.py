"""Tests for Ecovacs sensors."""

from deebot_client.command import Command
from deebot_client.commands.json import ResetLifeSpan, SetRelocationState
from deebot_client.events import LifeSpan
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.button.const import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = [
    pytest.mark.usefixtures("init_integration"),
    pytest.mark.freeze_time("2024-01-01 00:00:00"),
]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.BUTTON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("device_fixture", "entities"),
    [
        (
            "yna5x1",
            [
                ("button.ozmo_950_relocate", SetRelocationState()),
                (
                    "button.ozmo_950_reset_main_brush_lifespan",
                    ResetLifeSpan(LifeSpan.BRUSH),
                ),
                (
                    "button.ozmo_950_reset_filter_lifespan",
                    ResetLifeSpan(LifeSpan.FILTER),
                ),
                (
                    "button.ozmo_950_reset_side_brushes_lifespan",
                    ResetLifeSpan(LifeSpan.SIDE_BRUSH),
                ),
            ],
        ),
    ],
    ids=["yna5x1"],
)
async def test_buttons(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    controller: EcovacsController,
    entities: list[tuple[str, Command]],
) -> None:
    """Test that sensor entity snapshots match."""
    assert hass.states.async_entity_ids() == [e[0] for e in entities]
    device = controller.devices[0]
    for entity_id, command in entities:
        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert state.state == STATE_UNKNOWN

        device._execute_command.reset_mock()
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        device._execute_command.assert_called_with(command)

        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert state.state == "2024-01-01T00:00:00+00:00"
        assert snapshot(name=f"{entity_id}:state") == state

        assert (entity_entry := entity_registry.async_get(state.entity_id))
        assert snapshot(name=f"{entity_id}:entity-registry") == entity_entry

        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert device_entry.identifiers == {(DOMAIN, device.device_info.did)}


@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "yna5x1",
            [
                "button.ozmo_950_reset_main_brush_lifespan",
                "button.ozmo_950_reset_filter_lifespan",
                "button.ozmo_950_reset_side_brushes_lifespan",
            ],
        ),
    ],
)
async def test_disabled_by_default_buttons(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_ids: list[str]
) -> None:
    """Test the disabled by default buttons."""
    for entity_id in entity_ids:
        assert not hass.states.get(entity_id)

        assert (
            entry := entity_registry.async_get(entity_id)
        ), f"Entity registry entry for {entity_id} is missing"
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
