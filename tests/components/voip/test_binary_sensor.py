"""Test VoIP binary sensor devices."""

from http import HTTPStatus

import pytest

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.components.voip import DOMAIN
from homeassistant.components.voip.devices import VoIPDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_call_in_progress(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    voip_device: VoIPDevice,
) -> None:
    """Test call in progress."""
    state = hass.states.get("binary_sensor.192_168_1_210_call_in_progress")
    assert state is not None
    assert state.state == "off"

    voip_device.set_is_active(True)

    state = hass.states.get("binary_sensor.192_168_1_210_call_in_progress")
    assert state.state == "on"

    voip_device.set_is_active(False)

    state = hass.states.get("binary_sensor.192_168_1_210_call_in_progress")
    assert state.state == "off"


@pytest.mark.usefixtures("voip_device")
async def test_assist_in_progress_disabled_by_default(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test assist in progress binary sensor is added disabled."""

    assert not hass.states.get("binary_sensor.192_168_1_210_call_in_progress")
    entity_entry = entity_registry.async_get(
        "binary_sensor.192_168_1_210_call_in_progress"
    )
    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_assist_in_progress_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    voip_device: VoIPDevice,
) -> None:
    """Test assist in progress binary sensor."""

    call_in_progress_entity_id = "binary_sensor.192_168_1_210_call_in_progress"

    state = hass.states.get(call_in_progress_entity_id)
    assert state is not None

    entity_entry = entity_registry.async_get(call_in_progress_entity_id)
    issue = issue_registry.async_get_issue(
        DOMAIN, f"assist_in_progress_deprecated_{entity_entry.id}"
    )
    assert issue is not None

    # Test issue goes away after disabling the entity
    entity_registry.async_update_entity(
        call_in_progress_entity_id,
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
    voip_device: VoIPDevice,
) -> None:
    """Test assist in progress binary sensor deprecation issue flow."""

    call_in_progress_entity_id = "binary_sensor.192_168_1_210_call_in_progress"

    state = hass.states.get(call_in_progress_entity_id)
    assert state is not None

    entity_entry = entity_registry.async_get(call_in_progress_entity_id)
    assert entity_entry.disabled_by is None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"assist_in_progress_deprecated_{entity_entry.id}"
    )
    assert issue is not None
    assert issue.data == {
        "entity_id": call_in_progress_entity_id,
        "entity_uuid": entity_entry.id,
        "integration_name": "VoIP",
    }
    assert issue.translation_key == "assist_in_progress_deprecated"
    assert issue.translation_placeholders == {"integration_name": "VoIP"}

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
            "entity_id": call_in_progress_entity_id,
            "integration_name": "VoIP",
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
    entity_entry = entity_registry.async_get(call_in_progress_entity_id)
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.USER
