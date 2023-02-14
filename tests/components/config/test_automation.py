"""Test Automation config panel."""
from http import HTTPStatus
import json
from unittest.mock import patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401
from tests.typing import ClientSessionGenerator


@pytest.fixture
async def setup_automation(
    hass, automation_config, stub_blueprint_populate  # noqa: F811
):
    """Set up automation integration."""
    assert await async_setup_component(
        hass, "automation", {"automation": automation_config}
    )


@pytest.mark.parametrize("automation_config", ({},))
async def test_get_automation_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    setup_automation,
) -> None:
    """Test getting automation config."""
    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    hass_config_store["automations.yaml"] = [{"id": "sun"}, {"id": "moon"}]

    resp = await client.get("/api/config/automation/config/moon")

    assert resp.status == HTTPStatus.OK
    result = await resp.json()

    assert result == {"id": "moon"}


@pytest.mark.parametrize("automation_config", ({},))
async def test_update_automation_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    setup_automation,
) -> None:
    """Test updating automation config."""
    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("automation")) == []

    client = await hass_client()

    orig_data = [{"id": "sun"}, {"id": "moon"}]
    hass_config_store["automations.yaml"] = orig_data

    resp = await client.post(
        "/api/config/automation/config/moon",
        data=json.dumps({"trigger": [], "action": [], "condition": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("automation")) == [
        "automation.automation_0"
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    new_data = hass_config_store["automations.yaml"]
    assert list(new_data[1]) == ["id", "trigger", "condition", "action"]
    assert new_data[1] == {"id": "moon", "trigger": [], "condition": [], "action": []}


@pytest.mark.parametrize("automation_config", ({},))
async def test_update_automation_config_with_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    setup_automation,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test updating automation config with errors."""
    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("automation")) == []

    client = await hass_client()

    orig_data = [{"id": "sun"}, {"id": "moon"}]
    hass_config_store["automations.yaml"] = orig_data

    resp = await client.post(
        "/api/config/automation/config/moon",
        data=json.dumps({"action": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("automation")) == []

    assert resp.status != HTTPStatus.OK
    result = await resp.json()
    validation_error = "required key not provided @ data['trigger']"
    assert result == {"message": f"Message malformed: {validation_error}"}
    # Assert the validation error is not logged
    assert validation_error not in caplog.text


@pytest.mark.parametrize("automation_config", ({},))
async def test_update_remove_key_automation_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    setup_automation,
) -> None:
    """Test updating automation config while removing a key."""
    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("automation")) == []

    client = await hass_client()

    orig_data = [{"id": "sun", "key": "value"}, {"id": "moon", "key": "value"}]
    hass_config_store["automations.yaml"] = orig_data

    resp = await client.post(
        "/api/config/automation/config/moon",
        data=json.dumps({"trigger": [], "action": [], "condition": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("automation")) == [
        "automation.automation_0"
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    new_data = hass_config_store["automations.yaml"]
    assert list(new_data[1]) == ["id", "trigger", "condition", "action"]
    assert new_data[1] == {"id": "moon", "trigger": [], "condition": [], "action": []}


@pytest.mark.parametrize("automation_config", ({},))
async def test_bad_formatted_automations(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    setup_automation,
) -> None:
    """Test that we handle automations without ID."""
    with patch.object(config, "SECTIONS", ["automation"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("automation")) == []

    client = await hass_client()

    orig_data = [
        {
            # No ID
            "action": {"event": "hello"}
        },
        {"id": "moon"},
    ]
    hass_config_store["automations.yaml"] = orig_data

    resp = await client.post(
        "/api/config/automation/config/moon",
        data=json.dumps({"trigger": [], "action": [], "condition": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("automation")) == [
        "automation.automation_0"
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    # Verify ID added
    new_data = hass_config_store["automations.yaml"]
    assert "id" in new_data[0]
    assert new_data[1] == {"id": "moon", "trigger": [], "condition": [], "action": []}


@pytest.mark.parametrize(
    "automation_config",
    (
        [
            {
                "id": "sun",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation"},
            },
            {
                "id": "moon",
                "trigger": {"platform": "event", "event_type": "test_event"},
                "action": {"service": "test.automation"},
            },
        ],
    ),
)
async def test_delete_automation(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    setup_automation,
) -> None:
    """Test deleting an automation."""
    ent_reg = er.async_get(hass)

    assert len(ent_reg.entities) == 2

    with patch.object(config, "SECTIONS", ["automation"]):
        assert await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("automation")) == [
        "automation.automation_0",
        "automation.automation_1",
    ]

    client = await hass_client()

    orig_data = [{"id": "sun"}, {"id": "moon"}]
    hass_config_store["automations.yaml"] = orig_data

    resp = await client.delete("/api/config/automation/config/sun")
    await hass.async_block_till_done()

    assert sorted(hass.states.async_entity_ids("automation")) == [
        "automation.automation_1",
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert hass_config_store["automations.yaml"] == [{"id": "moon"}]

    assert len(ent_reg.entities) == 1
