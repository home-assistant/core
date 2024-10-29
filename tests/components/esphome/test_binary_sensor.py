"""Test ESPHome binary sensors."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus

from aioesphomeapi import (
    APIClient,
    BinarySensorInfo,
    BinarySensorState,
    EntityInfo,
    EntityState,
    UserService,
)
import pytest

from homeassistant.components.esphome import DOMAIN, DomainData
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import MockESPHomeDevice

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_assist_in_progress(
    hass: HomeAssistant,
    mock_voice_assistant_v1_entry,
) -> None:
    """Test assist in progress binary sensor."""

    entry_data = DomainData.get(hass).get_entry_data(mock_voice_assistant_v1_entry)

    state = hass.states.get("binary_sensor.test_assist_in_progress")
    assert state is not None
    assert state.state == "off"

    entry_data.async_set_assist_pipeline_state(True)

    state = hass.states.get("binary_sensor.test_assist_in_progress")
    assert state.state == "on"

    entry_data.async_set_assist_pipeline_state(False)

    state = hass.states.get("binary_sensor.test_assist_in_progress")
    assert state.state == "off"


async def test_assist_in_progress_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_voice_assistant_v1_entry,
) -> None:
    """Test assist in progress binary sensor is added disabled."""

    assert not hass.states.get("binary_sensor.test_assist_in_progress")
    entity_entry = entity_registry.async_get("binary_sensor.test_assist_in_progress")
    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test no issue for disabled entity
    assert len(issue_registry.issues) == 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_assist_in_progress_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_voice_assistant_v1_entry,
) -> None:
    """Test assist in progress binary sensor."""

    state = hass.states.get("binary_sensor.test_assist_in_progress")
    assert state is not None

    entity_entry = entity_registry.async_get("binary_sensor.test_assist_in_progress")
    issue = issue_registry.async_get_issue(
        DOMAIN, f"assist_in_progress_deprecated_{entity_entry.id}"
    )
    assert issue is not None

    # Test issue goes away after disabling the entity
    entity_registry.async_update_entity(
        "binary_sensor.test_assist_in_progress",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await hass.async_block_till_done()
    issue = issue_registry.async_get_issue(
        DOMAIN, f"assist_in_progress_deprecated_{entity_entry.id}"
    )
    assert issue is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_assist_in_progress_repair_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_voice_assistant_v1_entry,
) -> None:
    """Test assist in progress binary sensor deprecation issue flow."""

    state = hass.states.get("binary_sensor.test_assist_in_progress")
    assert state is not None

    entity_entry = entity_registry.async_get("binary_sensor.test_assist_in_progress")
    assert entity_entry.disabled_by is None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"assist_in_progress_deprecated_{entity_entry.id}"
    )
    assert issue is not None
    assert issue.data == {
        "entity_id": "binary_sensor.test_assist_in_progress",
        "entity_uuid": entity_entry.id,
        "integration_name": "ESPHome",
    }
    assert issue.translation_key == "assist_in_progress_deprecated"
    assert issue.translation_placeholders == {"integration_name": "ESPHome"}

    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})
    await hass.async_block_till_done()
    await hass.async_start()

    client = await hass_client()

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": DOMAIN, "issue_id": issue.issue_id},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "data_schema": [],
        "description_placeholders": {
            "assist_satellite_domain": "assist_satellite",
            "entity_id": "binary_sensor.test_assist_in_progress",
            "integration_name": "ESPHome",
        },
        "errors": None,
        "flow_id": flow_id,
        "handler": DOMAIN,
        "last_step": None,
        "preview": None,
        "step_id": "confirm_disable_entity",
        "type": "form",
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "description": None,
        "description_placeholders": None,
        "flow_id": flow_id,
        "handler": DOMAIN,
        "type": "create_entry",
    }

    # Test the entity is disabled
    entity_entry = entity_registry.async_get("binary_sensor.test_assist_in_progress")
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.USER


@pytest.mark.parametrize(
    "binary_state", [(True, STATE_ON), (False, STATE_OFF), (None, STATE_UNKNOWN)]
)
async def test_binary_sensor_generic_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    binary_state: tuple[bool, str],
    mock_generic_device_entry: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockConfigEntry],
    ],
) -> None:
    """Test a generic binary_sensor entity."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
        )
    ]
    esphome_state, hass_state = binary_state
    states = [BinarySensorState(key=1, state=esphome_state)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == hass_state


async def test_status_binary_sensor(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockConfigEntry],
    ],
) -> None:
    """Test a generic binary_sensor entity."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
            is_status_binary_sensor=True,
        )
    ]
    states = [BinarySensorState(key=1, state=None)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensor_missing_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockConfigEntry],
    ],
) -> None:
    """Test a generic binary_sensor that is missing state."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
        )
    ]
    states = [BinarySensorState(key=1, state=True, missing_state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_binary_sensor_has_state_false(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a generic binary_sensor where has_state is false."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
        )
    ]
    states = []
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    mock_device.set_state(BinarySensorState(key=1, state=True, missing_state=False))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON
