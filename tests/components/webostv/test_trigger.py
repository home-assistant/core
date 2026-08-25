"""The tests for LG webOS TV automation triggers."""

import asyncio
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import attr
import pytest

from homeassistant.components import automation
from homeassistant.components.webostv import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component

from . import setup_webostv
from .const import ENTITY_ID, FAKE_UUID

from tests.common import MockEntity, MockEntityPlatform

TURN_ON_REQUESTED = "webostv.turn_on_requested"
LEGACY_TURN_ON = "webostv.turn_on"


@pytest.mark.parametrize(
    "build_trigger",
    [
        pytest.param(
            lambda device_id: {"trigger": LEGACY_TURN_ON, "device_id": device_id},
            id="legacy",
        ),
        pytest.param(
            lambda device_id: {
                "trigger": TURN_ON_REQUESTED,
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
    entry = await setup_webostv(hass)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, FAKE_UUID), entry.entry_id
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
        pytest.param({"trigger": LEGACY_TURN_ON, "entity_id": ENTITY_ID}, id="legacy"),
        pytest.param(
            {"trigger": TURN_ON_REQUESTED, "target": {"entity_id": ENTITY_ID}},
            id="target",
        ),
        pytest.param(
            # The shape the automation editor writes when saving a new trigger
            {
                "trigger": TURN_ON_REQUESTED,
                "target": {"entity_id": ENTITY_ID},
                "options": {},
            },
            id="target_with_empty_options",
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


@pytest.mark.usefixtures("client")
async def test_legacy_trigger_rejects_target(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the legacy trigger does not accept a target."""
    await setup_webostv(hass)

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "trigger": LEGACY_TURN_ON,
                        "target": {"entity_id": ENTITY_ID},
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ENTITY_ID},
                    },
                },
            ],
        },
    )

    assert "not a valid option at 'target'" in caplog.text


@pytest.mark.parametrize(
    "build_trigger",
    [
        pytest.param(
            lambda device_id: {"trigger": LEGACY_TURN_ON, "device_id": device_id},
            id="legacy",
        ),
        pytest.param(
            lambda device_id: {
                "trigger": TURN_ON_REQUESTED,
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
    entry = await setup_webostv(hass)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, FAKE_UUID), entry.entry_id
    )
    # Hidden entities are excluded when expanding a device target
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
    entry = await setup_webostv(hass)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, FAKE_UUID), entry.entry_id
    )
    composite_device_id = "composite00000000000000000000ab"
    device_registry._devices[device.id] = attr.evolve(
        device, composite_device_id=composite_device_id
    )
    # Hide entities so the composite id resolves only via device registry
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
                        "trigger": TURN_ON_REQUESTED,
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
                        "trigger": TURN_ON_REQUESTED,
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
async def test_webostv_turn_on_trigger_area_id(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test for turn_on triggers targeting an area firing."""
    entry = await setup_webostv(hass)

    area = area_registry.async_create("Living room")
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, FAKE_UUID), entry.entry_id
    )
    device_registry.async_update_device(device.id, area_id=area.id)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "trigger": TURN_ON_REQUESTED,
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
    entry = await setup_webostv(hass)

    area = area_registry.async_create("Living room")
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, FAKE_UUID), entry.entry_id
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "trigger": TURN_ON_REQUESTED,
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

    # TV isn't in the targeted area yet, so no action is attached
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
                        "trigger": TURN_ON_REQUESTED,
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


@pytest.mark.parametrize(
    "trigger_config",
    [
        pytest.param({"trigger": LEGACY_TURN_ON, "entity_id": ENTITY_ID}, id="legacy"),
        pytest.param(
            {"trigger": TURN_ON_REQUESTED, "target": {"entity_id": ENTITY_ID}},
            id="target",
        ),
    ],
)
@pytest.mark.usefixtures("client")
async def test_turn_on_waits_for_the_automation(
    hass: HomeAssistant, trigger_config: dict[str, Any]
) -> None:
    """Test the turn on service waits for the triggered automation to finish."""
    await setup_webostv(hass)

    started = asyncio.Event()
    finish = asyncio.Event()

    async def slow_action(call: ServiceCall) -> None:
        started.set()
        await finish.wait()

    hass.services.async_register("slowtest", "run", slow_action)

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": trigger_config,
                    "action": {"service": "slowtest.run"},
                },
            ],
        },
    )

    turn_on = hass.async_create_task(
        hass.services.async_call(
            "media_player",
            "turn_on",
            {"entity_id": ENTITY_ID},
            blocking=True,
        )
    )
    await started.wait()

    assert not turn_on.done()

    finish.set()
    await turn_on


@pytest.mark.usefixtures("client")
async def test_legacy_trigger_invalid_entity_id(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the legacy trigger still rejects an entity of another integration."""
    await setup_webostv(hass)

    platform = MockEntityPlatform(hass)

    invalid_entity = f"{DOMAIN}.invalid"
    await platform.async_add_entities([MockEntity(name=invalid_entity)])

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "trigger": LEGACY_TURN_ON,
                        "entity_id": invalid_entity,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ENTITY_ID},
                    },
                },
            ],
        },
    )

    assert f"Entity {invalid_entity} is not a valid webOS TV entity" in caplog.text


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
                    "trigger": {"trigger": TURN_ON_REQUESTED, "target": {}},
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ENTITY_ID},
                    },
                },
            ],
        },
    )

    assert "The LG webOS TV turn on trigger requires a target" in caplog.text
