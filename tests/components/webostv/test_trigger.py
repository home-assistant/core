"""The tests for LG webOS TV automation triggers."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import attr
import pytest

from homeassistant.components import automation
from homeassistant.components.webostv import DOMAIN
from homeassistant.components.webostv.triggers.turn_on import DEPRECATED_TARGET_ISSUE_ID
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from . import setup_webostv
from .const import ENTITY_ID, FAKE_UUID

from tests.common import MockEntity, MockEntityPlatform


@pytest.mark.parametrize(
    "build_trigger",
    [
        pytest.param(
            lambda device_id: {"trigger": "webostv.turn_on", "device_id": device_id},
            id="legacy",
        ),
        pytest.param(
            lambda device_id: {
                "trigger": "webostv.turn_on",
                "target": {"device_id": device_id},
            },
            id="target",
        ),
    ],
)
@pytest.mark.usefixtures("client")
async def test_webostv_turn_on_trigger_device_id(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    build_trigger: Callable[[str], dict[str, Any]],
) -> None:
    """Test for turn_on triggers by device_id firing."""
    await setup_webostv(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, FAKE_UUID)})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": build_trigger(device.id),
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": device.id,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == device.id
    assert service_calls[1].data["id"] == 0

    with patch("homeassistant.config.load_yaml_dict", return_value={}):
        await hass.services.async_call(automation.DOMAIN, SERVICE_RELOAD, blocking=True)

    service_calls.clear()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "turn_on",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )

    assert len(service_calls) == 1


@pytest.mark.parametrize(
    "trigger_config",
    [
        pytest.param(
            {"trigger": "webostv.turn_on", "entity_id": ENTITY_ID}, id="legacy"
        ),
        pytest.param(
            {"trigger": "webostv.turn_on", "target": {"entity_id": ENTITY_ID}},
            id="target",
        ),
        pytest.param(
            {"trigger": "webostv.turn_on", "entity_id": ENTITY_ID, "target": {}},
            id="legacy_with_empty_target",
        ),
        pytest.param(
            {
                "trigger": "webostv.turn_on",
                "entity_id": ENTITY_ID,
                "target": {"entity_id": []},
            },
            id="legacy_with_empty_target_value",
        ),
        pytest.param(
            {
                "trigger": "webostv.turn_on",
                "entity_id": f"{ENTITY_ID},media_player.other",
            },
            id="legacy_comma_separated",
        ),
        pytest.param(
            {"trigger": "webostv.turn_on", "entity_id": ENTITY_ID.upper()},
            id="legacy_uppercase",
        ),
    ],
)
@pytest.mark.usefixtures("client")
async def test_webostv_turn_on_trigger_entity_id(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_config: dict[str, Any],
) -> None:
    """Test for turn_on triggers by entity_id firing."""
    await setup_webostv(hass)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": trigger_config,
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": ENTITY_ID,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == ENTITY_ID
    assert service_calls[1].data["id"] == 0


@pytest.mark.parametrize(
    "build_trigger",
    [
        pytest.param(
            lambda device_id: {"trigger": "webostv.turn_on", "device_id": device_id},
            id="legacy",
        ),
        pytest.param(
            lambda device_id: {
                "trigger": "webostv.turn_on",
                "target": {"device_id": device_id},
            },
            id="target",
        ),
    ],
)
@pytest.mark.usefixtures("client")
async def test_webostv_turn_on_trigger_hidden_entity(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    build_trigger: Callable[[str], dict[str, Any]],
) -> None:
    """Test a device target still fires when the device entities are hidden."""
    await setup_webostv(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, FAKE_UUID)})
    # Hidden entities are excluded when a device target is expanded to its entities
    for entry in er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    ):
        entity_registry.async_update_entity(
            entry.entity_id, hidden_by=er.RegistryEntryHider.USER
        )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": build_trigger(device.id),
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "{{ trigger.device_id }}"},
                    },
                },
            ],
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == device.id


@pytest.mark.usefixtures("client")
async def test_webostv_turn_on_trigger_composite_device_id(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a target using a pre-migration composite device id."""
    await setup_webostv(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, FAKE_UUID)})
    composite_device_id = "composite00000000000000000000ab"
    device_registry.devices[device.id] = attr.evolve(
        device, composite_device_id=composite_device_id
    )
    # Hide the entities so the composite id can only resolve through the device registry
    for entry in er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    ):
        entity_registry.async_update_entity(
            entry.entity_id, hidden_by=er.RegistryEntryHider.USER
        )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "trigger": "webostv.turn_on",
                        "target": {"device_id": composite_device_id},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "{{ trigger.device_id }}"},
                    },
                },
            ],
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == device.id


@pytest.mark.usefixtures("client")
async def test_webostv_turn_on_trigger_area_id(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test for turn_on triggers targeting an area firing."""
    await setup_webostv(hass)

    area = area_registry.async_create("Living room")
    device = device_registry.async_get_device(identifiers={(DOMAIN, FAKE_UUID)})
    device_registry.async_update_device(device.id, area_id=area.id)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "trigger": "webostv.turn_on",
                        "target": {"area_id": area.id},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "{{ trigger.device_id }}"},
                    },
                },
            ],
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == device.id


@pytest.mark.usefixtures("client")
async def test_webostv_turn_on_trigger_follows_area_changes(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the targeted devices are updated when the device area changes."""
    await setup_webostv(hass)

    area = area_registry.async_create("Living room")
    device = device_registry.async_get_device(identifiers={(DOMAIN, FAKE_UUID)})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "trigger": "webostv.turn_on",
                        "target": {"area_id": area.id},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "{{ trigger.device_id }}"},
                    },
                },
            ],
        },
    )
    await hass.async_block_till_done()

    # The TV is not in the targeted area yet, so no turn on action is attached
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "turn_on",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )

    assert len(service_calls) == 1

    device_registry.async_update_device(device.id, area_id=area.id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "media_player",
        "turn_on",
        {"entity_id": ENTITY_ID},
        blocking=True,
    )

    assert len(service_calls) == 3
    assert service_calls[2].data["some"] == device.id

    device_registry.async_update_device(device.id, area_id=None)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "turn_on",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )

    assert len(service_calls) == 4


@pytest.mark.usefixtures("client")
async def test_unknown_trigger_platform_type(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test unknown trigger platform type."""
    await setup_webostv(hass)

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "webostv.unknown",
                        "entity_id": ENTITY_ID,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": ENTITY_ID,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )

    assert "Invalid trigger 'webostv.unknown' specified" in caplog.text


@pytest.mark.parametrize(
    "build_legacy_option",
    [
        pytest.param(lambda device_id: {"entity_id": ENTITY_ID}, id="entity_id"),
        pytest.param(lambda device_id: {"device_id": device_id}, id="device_id"),
    ],
)
@pytest.mark.usefixtures("client")
async def test_trigger_target_takes_precedence_over_legacy(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    build_legacy_option: Callable[[str], dict[str, Any]],
) -> None:
    """Test the target wins over a legacy option selecting another device."""
    await setup_webostv(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, FAKE_UUID)})

    platform = MockEntityPlatform(hass)
    other_entity = f"{DOMAIN}.other"
    await platform.async_add_entities([MockEntity(name=other_entity)])

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "trigger": "webostv.turn_on",
                        **build_legacy_option(device.id),
                        "target": {"entity_id": other_entity},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ENTITY_ID},
                    },
                },
            ],
        },
    )

    # The target selects another entity, so the legacy entity_id is not used
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "turn_on",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )

    assert len(service_calls) == 1


@pytest.mark.usefixtures("client")
async def test_trigger_unknown_device_id(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test turn on trigger targeting a device that no longer exists."""
    await setup_webostv(hass)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "trigger": "webostv.turn_on",
                        "target": {"device_id": "does-not-exist"},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ENTITY_ID},
                    },
                },
            ],
        },
    )

    assert "ValueError" not in caplog.text

    # The device does not resolve, so no turn on action is attached
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "turn_on",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )

    assert len(service_calls) == 1


@pytest.mark.usefixtures("client")
async def test_trigger_non_webostv_entity_id(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test turn on trigger using an entity_id of another integration."""
    await setup_webostv(hass)

    platform = MockEntityPlatform(hass)

    invalid_entity = f"{DOMAIN}.invalid"
    await platform.async_add_entities([MockEntity(name=invalid_entity)])

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "trigger": "webostv.turn_on",
                        "target": {"entity_id": invalid_entity},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ENTITY_ID},
                    },
                },
            ],
        },
    )

    # The entity is not a webOS TV entity, so no turn on trigger is attached
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "turn_on",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )

    assert len(service_calls) == 1


@pytest.mark.usefixtures("client")
async def test_trigger_without_target(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test turn on trigger without a target."""
    await setup_webostv(hass)

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"trigger": "webostv.turn_on", "target": {}},
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ENTITY_ID},
                    },
                },
            ],
        },
    )

    assert "The LG webOS TV turn on trigger requires a target" in caplog.text


@pytest.mark.parametrize(
    ("trigger_config", "issue_expected"),
    [
        pytest.param(
            {"trigger": "webostv.turn_on", "entity_id": ENTITY_ID}, True, id="entity_id"
        ),
        pytest.param(
            {"trigger": "webostv.turn_on", "device_id": "some-device-id"},
            True,
            id="device_id",
        ),
        pytest.param(
            {"trigger": "webostv.turn_on", "target": {"entity_id": ENTITY_ID}},
            False,
            id="target",
        ),
    ],
)
@pytest.mark.usefixtures("client")
async def test_deprecated_target_repair_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    trigger_config: dict[str, Any],
    issue_expected: bool,
) -> None:
    """Test the repair issue raised for the legacy top-level trigger options."""
    await setup_webostv(hass)

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": trigger_config,
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ENTITY_ID},
                    },
                },
            ],
        },
    )

    issue = issue_registry.async_get_issue(DOMAIN, DEPRECATED_TARGET_ISSUE_ID)
    assert (issue is not None) is issue_expected
