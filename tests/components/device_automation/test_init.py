"""The test for light device automation."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_unordered import unordered
import voluptuous as vol

from homeassistant import config_entries, loader
from homeassistant.components import device_automation
import homeassistant.components.automation as automation
from homeassistant.components.device_automation import (
    InvalidDeviceAutomationConfig,
    toggle_entity,
)
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import IntegrationNotFound
from homeassistant.requirements import RequirementsNotFound
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    async_mock_service,
    mock_integration,
    mock_platform,
)
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
def fake_integration(hass):
    """Set up a mock integration with device automation support."""
    DOMAIN = "fake_integration"

    hass.config.components.add(DOMAIN)

    async def _async_get_actions(
        hass: HomeAssistant, device_id: str
    ) -> list[dict[str, str]]:
        """List device actions."""
        return await toggle_entity.async_get_actions(hass, device_id, DOMAIN)

    async def _async_get_conditions(
        hass: HomeAssistant, device_id: str
    ) -> list[dict[str, str]]:
        """List device conditions."""
        return await toggle_entity.async_get_conditions(hass, device_id, DOMAIN)

    async def _async_get_triggers(
        hass: HomeAssistant, device_id: str
    ) -> list[dict[str, str]]:
        """List device triggers."""
        return await toggle_entity.async_get_triggers(hass, device_id, DOMAIN)

    mock_platform(
        hass,
        f"{DOMAIN}.device_action",
        Mock(
            ACTION_SCHEMA=toggle_entity.ACTION_SCHEMA.extend(
                {vol.Required("domain"): DOMAIN}
            ),
            async_get_actions=_async_get_actions,
            spec=["ACTION_SCHEMA", "async_get_actions"],
        ),
    )

    mock_platform(
        hass,
        f"{DOMAIN}.device_condition",
        Mock(
            CONDITION_SCHEMA=toggle_entity.CONDITION_SCHEMA.extend(
                {vol.Required("domain"): DOMAIN}
            ),
            async_get_conditions=_async_get_conditions,
            spec=["CONDITION_SCHEMA", "async_get_conditions"],
        ),
    )

    mock_platform(
        hass,
        f"{DOMAIN}.device_trigger",
        Mock(
            TRIGGER_SCHEMA=vol.All(
                toggle_entity.TRIGGER_SCHEMA,
                vol.Schema({vol.Required("domain"): DOMAIN}, extra=vol.ALLOW_EXTRA),
            ),
            async_get_triggers=_async_get_triggers,
            spec=["TRIGGER_SCHEMA", "async_get_triggers"],
        ),
    )


async def test_websocket_get_actions(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get the expected actions through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        "fake_integration", "test", "5678", device_id=device_entry.id
    )
    expected_actions = [
        {
            "domain": "fake_integration",
            "type": "turn_off",
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        },
        {
            "domain": "fake_integration",
            "type": "turn_on",
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        },
        {
            "domain": "fake_integration",
            "type": "toggle",
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        },
    ]

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "device_automation/action/list", "device_id": device_entry.id}
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    actions = msg["result"]
    assert actions == unordered(expected_actions)


async def test_websocket_get_conditions(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get the expected conditions through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        "fake_integration", "test", "5678", device_id=device_entry.id
    )
    expected_conditions = [
        {
            "condition": "device",
            "domain": "fake_integration",
            "type": "is_off",
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        },
        {
            "condition": "device",
            "domain": "fake_integration",
            "type": "is_on",
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        },
    ]

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/condition/list",
            "device_id": device_entry.id,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    conditions = msg["result"]
    assert conditions == unordered(expected_conditions)


async def test_websocket_get_triggers(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get the expected triggers through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        "fake_integration", "test", "5678", device_id=device_entry.id
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": "fake_integration",
            "type": "changed_states",
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        },
        {
            "platform": "device",
            "domain": "fake_integration",
            "type": "turned_off",
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        },
        {
            "platform": "device",
            "domain": "fake_integration",
            "type": "turned_on",
            "device_id": device_entry.id,
            "entity_id": entity_entry.id,
            "metadata": {"secondary": False},
        },
    ]

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/trigger/list",
            "device_id": device_entry.id,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    triggers = msg["result"]
    assert triggers == unordered(expected_triggers)


async def test_websocket_get_action_capabilities(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get the expected action capabilities through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        "fake_integration", "test", "5678", device_id=device_entry.id
    )
    expected_capabilities = {
        "turn_on": {
            "extra_fields": [{"type": "string", "name": "code", "optional": True}]
        },
        "turn_off": {"extra_fields": []},
        "toggle": {"extra_fields": []},
    }

    async def _async_get_action_capabilities(
        hass: HomeAssistant, config: ConfigType
    ) -> dict[str, vol.Schema]:
        """List action capabilities."""
        if config["type"] == "turn_on":
            return {"extra_fields": vol.Schema({vol.Optional("code"): str})}
        return {}

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_action"]
    module.async_get_action_capabilities = _async_get_action_capabilities

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "device_automation/action/list", "device_id": device_entry.id}
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    actions = msg["result"]

    id = 2
    assert len(actions) == 3
    for action in actions:
        await client.send_json(
            {
                "id": id,
                "type": "device_automation/action/capabilities",
                "action": action,
            }
        )
        msg = await client.receive_json()
        assert msg["id"] == id
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]
        capabilities = msg["result"]
        assert capabilities == expected_capabilities[action["type"]]
        id = id + 1


async def test_websocket_get_action_capabilities_unknown_domain(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get no action capabilities for a non existing domain."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/action/capabilities",
            "action": {"domain": "beer"},
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_websocket_get_action_capabilities_no_capabilities(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get no action capabilities for a domain which has none.

    The tests tests a domain which has a device action platform, but no
    async_get_action_capabilities.
    """
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/action/capabilities",
            "action": {"domain": "fake_integration"},
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_websocket_get_action_capabilities_bad_action(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get no action capabilities when there is an error."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_action"]
    module.async_get_action_capabilities = Mock(
        side_effect=InvalidDeviceAutomationConfig
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/action/capabilities",
            "action": {"domain": "fake_integration"},
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities
    module.async_get_action_capabilities.assert_called_once()


async def test_websocket_get_condition_capabilities(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get the expected condition capabilities through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        "fake_integration", "test", "5678", device_id=device_entry.id
    )
    expected_capabilities = {
        "extra_fields": [
            {"name": "for", "optional": True, "type": "positive_time_period_dict"}
        ]
    }

    async def _async_get_condition_capabilities(
        hass: HomeAssistant, config: ConfigType
    ) -> dict[str, vol.Schema]:
        """List condition capabilities."""
        return await toggle_entity.async_get_condition_capabilities(hass, config)

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_condition"]
    module.async_get_condition_capabilities = _async_get_condition_capabilities

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/condition/list",
            "device_id": device_entry.id,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    conditions = msg["result"]

    id = 2
    assert len(conditions) == 2
    for condition in conditions:
        await client.send_json(
            {
                "id": id,
                "type": "device_automation/condition/capabilities",
                "condition": condition,
            }
        )
        msg = await client.receive_json()
        assert msg["id"] == id
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]
        capabilities = msg["result"]
        assert capabilities == expected_capabilities
        id = id + 1


async def test_websocket_get_condition_capabilities_unknown_domain(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get no condition capabilities for a non existing domain."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/condition/capabilities",
            "condition": {"condition": "device", "domain": "beer", "device_id": "1234"},
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_websocket_get_condition_capabilities_no_capabilities(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get no condition capabilities for a domain which has none.

    The tests tests a domain which has a device condition platform, but no
    async_get_condition_capabilities.
    """
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/condition/capabilities",
            "condition": {
                "condition": "device",
                "device_id": "abcd",
                "domain": "fake_integration",
            },
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_websocket_get_condition_capabilities_bad_condition(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get no condition capabilities when there is an error."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_condition"]
    module.async_get_condition_capabilities = Mock(
        side_effect=InvalidDeviceAutomationConfig
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/condition/capabilities",
            "condition": {
                "condition": "device",
                "device_id": "abcd",
                "domain": "fake_integration",
            },
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities
    module.async_get_condition_capabilities.assert_called_once()


async def test_async_get_device_automations_single_device_trigger(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get can fetch the triggers for a device id."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        "light", "test", "5678", device_id=device_entry.id
    )
    result = await device_automation.async_get_device_automations(
        hass, device_automation.DeviceAutomationType.TRIGGER, [device_entry.id]
    )
    assert device_entry.id in result
    assert len(result[device_entry.id]) == 3


async def test_async_get_device_automations_all_devices_trigger(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get can fetch all the triggers when no device id is passed."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        "light", "test", "5678", device_id=device_entry.id
    )
    result = await device_automation.async_get_device_automations(
        hass, device_automation.DeviceAutomationType.TRIGGER
    )
    assert device_entry.id in result
    assert len(result[device_entry.id]) == 3  # toggled, turned_on, turned_off


async def test_async_get_device_automations_all_devices_condition(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get can fetch all the conditions when no device id is passed."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        "light", "test", "5678", device_id=device_entry.id
    )
    result = await device_automation.async_get_device_automations(
        hass, device_automation.DeviceAutomationType.CONDITION
    )
    assert device_entry.id in result
    assert len(result[device_entry.id]) == 2


async def test_async_get_device_automations_all_devices_action(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get can fetch all the actions when no device id is passed."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        "light", "test", "5678", device_id=device_entry.id
    )
    result = await device_automation.async_get_device_automations(
        hass, device_automation.DeviceAutomationType.ACTION
    )
    assert device_entry.id in result
    assert len(result[device_entry.id]) == 3


async def test_async_get_device_automations_all_devices_action_exception_throw(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we get can fetch all the actions when no device id is passed and can handle one throwing an exception."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        "light", "test", "5678", device_id=device_entry.id
    )
    with patch(
        "homeassistant.components.light.device_trigger.async_get_triggers",
        side_effect=KeyError,
    ):
        result = await device_automation.async_get_device_automations(
            hass, device_automation.DeviceAutomationType.TRIGGER
        )
    assert device_entry.id in result
    assert len(result[device_entry.id]) == 0
    assert "KeyError" in caplog.text


async def test_websocket_get_trigger_capabilities(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get the expected trigger capabilities through websocket."""
    await async_setup_component(hass, "device_automation", {})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        "fake_integration", "test", "5678", device_id=device_entry.id
    )
    expected_capabilities = {
        "extra_fields": [
            {"name": "for", "optional": True, "type": "positive_time_period_dict"}
        ]
    }

    async def _async_get_trigger_capabilities(
        hass: HomeAssistant, config: ConfigType
    ) -> dict[str, vol.Schema]:
        """List trigger capabilities."""
        return await toggle_entity.async_get_trigger_capabilities(hass, config)

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_trigger"]
    module.async_get_trigger_capabilities = _async_get_trigger_capabilities

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/trigger/list",
            "device_id": device_entry.id,
        }
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    triggers = msg["result"]

    id = 2
    assert len(triggers) == 3  # toggled, turned_on, turned_off
    for trigger in triggers:
        await client.send_json(
            {
                "id": id,
                "type": "device_automation/trigger/capabilities",
                "trigger": trigger,
            }
        )
        msg = await client.receive_json()
        assert msg["id"] == id
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]
        capabilities = msg["result"]
        assert capabilities == expected_capabilities
        id = id + 1


async def test_websocket_get_trigger_capabilities_unknown_domain(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get no trigger capabilities for a non existing domain."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/trigger/capabilities",
            "trigger": {"platform": "device", "domain": "beer", "device_id": "abcd"},
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_websocket_get_trigger_capabilities_no_capabilities(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get no trigger capabilities for a domain which has none.

    The tests tests a domain which has a device trigger platform, but no
    async_get_trigger_capabilities.
    """
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/trigger/capabilities",
            "trigger": {
                "platform": "device",
                "device_id": "abcd",
                "domain": "fake_integration",
            },
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities


async def test_websocket_get_trigger_capabilities_bad_trigger(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test we get no trigger capabilities when there is an error."""
    await async_setup_component(hass, "device_automation", {})
    expected_capabilities = {}

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_trigger"]
    module.async_get_trigger_capabilities = Mock(
        side_effect=InvalidDeviceAutomationConfig
    )

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "device_automation/trigger/capabilities",
            "trigger": {
                "platform": "device",
                "device_id": "abcd",
                "domain": "fake_integration",
            },
        }
    )
    msg = await client.receive_json()
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    capabilities = msg["result"]
    assert capabilities == expected_capabilities
    module.async_get_trigger_capabilities.assert_called_once()


async def test_automation_with_non_existing_integration(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test device automation trigger with non existing integration."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {
                    "platform": "device",
                    "device_id": "none",
                    "domain": "beer",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert "Integration 'beer' not found" in caplog.text


async def test_automation_with_device_action(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, fake_integration
) -> None:
    """Test automation with a device action."""

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_action"]
    module.async_call_action_from_config = AsyncMock()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "action": {
                    "device_id": "",
                    "domain": "fake_integration",
                    "entity_id": "blah.blah",
                    "type": "turn_on",
                },
            }
        },
    )

    module.async_call_action_from_config.assert_not_called()

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()

    module.async_call_action_from_config.assert_awaited_once()


async def test_automation_with_dynamically_validated_action(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
    fake_integration,
) -> None:
    """Test device automation with an action which is dynamically validated."""

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_action"]
    module.async_validate_action_config = AsyncMock()

    config_entry = MockConfigEntry(domain="fake_integration", data={})
    config_entry.state = config_entries.ConfigEntryState.LOADED
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "action": {"device_id": device_entry.id, "domain": "fake_integration"},
            }
        },
    )

    module.async_validate_action_config.assert_awaited_once()


async def test_automation_with_integration_without_device_action(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test device automation action with integration without device action support."""
    mock_integration(hass, MockModule(domain="test"))
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "action": {"device_id": "", "domain": "test"},
            }
        },
    )

    assert (
        "Integration 'test' does not support device automation actions" in caplog.text
    )


async def test_automation_with_device_condition(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, fake_integration
) -> None:
    """Test automation with a device condition."""

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_condition"]
    module.async_condition_from_config = Mock()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "condition": {
                    "condition": "device",
                    "device_id": "none",
                    "domain": "fake_integration",
                    "entity_id": "blah.blah",
                    "type": "is_on",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    module.async_condition_from_config.assert_called_once()


async def test_automation_with_dynamically_validated_condition(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
    fake_integration,
) -> None:
    """Test device automation with a condition which is dynamically validated."""

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_condition"]
    module.async_validate_condition_config = AsyncMock()

    config_entry = MockConfigEntry(domain="fake_integration", data={})
    config_entry.state = config_entries.ConfigEntryState.LOADED
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "condition": {
                    "condition": "device",
                    "device_id": device_entry.id,
                    "domain": "fake_integration",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    module.async_validate_condition_config.assert_awaited_once()


async def test_automation_with_integration_without_device_condition(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test device automation condition with integration without device condition support."""
    mock_integration(hass, MockModule(domain="test"))
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "condition": {
                    "condition": "device",
                    "device_id": "none",
                    "domain": "test",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert (
        "Integration 'test' does not support device automation conditions"
        in caplog.text
    )


async def test_automation_with_device_trigger(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, fake_integration
) -> None:
    """Test automation with a device trigger."""

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_trigger"]
    module.async_attach_trigger = AsyncMock()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {
                    "platform": "device",
                    "device_id": "none",
                    "domain": "fake_integration",
                    "entity_id": "blah.blah",
                    "type": "turned_off",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    module.async_attach_trigger.assert_awaited_once()


async def test_automation_with_dynamically_validated_trigger(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    fake_integration,
) -> None:
    """Test device automation with a trigger which is dynamically validated."""

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_trigger"]
    module.async_attach_trigger = AsyncMock()
    module.async_validate_trigger_config = AsyncMock(wraps=lambda hass, config: config)

    config_entry = MockConfigEntry(domain="fake_integration", data={})
    config_entry.state = config_entries.ConfigEntryState.LOADED
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_registry.async_get_or_create(
        "fake_integration", "test", "5678", device_id=device_entry.id
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {
                    "platform": "device",
                    "device_id": device_entry.id,
                    "domain": "fake_integration",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    module.async_validate_trigger_config.assert_awaited_once()
    module.async_attach_trigger.assert_awaited_once()


async def test_automation_with_integration_without_device_trigger(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test device automation trigger with integration without device trigger support."""
    mock_integration(hass, MockModule(domain="test"))
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {
                    "platform": "device",
                    "device_id": "none",
                    "domain": "test",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert (
        "Integration 'test' does not support device automation triggers" in caplog.text
    )


async def test_automation_with_bad_action(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation with bad device action."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "action": {"device_id": "", "domain": "light"},
            }
        },
    )

    assert "required key not provided" in caplog.text


async def test_automation_with_bad_condition_action(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation with bad device action."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "action": {"condition": "device", "device_id": "", "domain": "light"},
            }
        },
    )

    assert "required key not provided" in caplog.text


async def test_automation_with_bad_condition_missing_domain(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation with bad device condition."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "condition": {"condition": "device", "device_id": "hello.device"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert "required key not provided @ data['condition'][0]['domain']" in caplog.text


async def test_automation_with_bad_condition(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation with bad device condition."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "condition": {"condition": "device", "domain": "light"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert "required key not provided" in caplog.text


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_automation_with_sub_condition(
    hass: HomeAssistant, calls, enable_custom_integrations: None
) -> None:
    """Test automation with device condition under and/or conditions."""
    DOMAIN = "light"
    platform = getattr(hass.components, f"test.{DOMAIN}")

    platform.init()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()
    ent1, ent2, ent3 = platform.ENTITIES

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "and",
                            "conditions": [
                                {
                                    "condition": "device",
                                    "domain": DOMAIN,
                                    "device_id": "",
                                    "entity_id": ent1.entity_id,
                                    "type": "is_on",
                                },
                                {
                                    "condition": "device",
                                    "domain": DOMAIN,
                                    "device_id": "",
                                    "entity_id": ent2.entity_id,
                                    "type": "is_on",
                                },
                            ],
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "and {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(("platform", "event.event_type"))
                        },
                    },
                },
                {
                    "trigger": {"platform": "event", "event_type": "test_event1"},
                    "condition": [
                        {
                            "condition": "or",
                            "conditions": [
                                {
                                    "condition": "device",
                                    "domain": DOMAIN,
                                    "device_id": "",
                                    "entity_id": ent1.entity_id,
                                    "type": "is_on",
                                },
                                {
                                    "condition": "device",
                                    "domain": DOMAIN,
                                    "device_id": "",
                                    "entity_id": ent2.entity_id,
                                    "type": "is_on",
                                },
                            ],
                        }
                    ],
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "or {{ trigger.%s }}"
                            % "}} - {{ trigger.".join(("platform", "event.event_type"))
                        },
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(ent1.entity_id).state == STATE_ON
    assert hass.states.get(ent2.entity_id).state == STATE_OFF
    assert len(calls) == 0

    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "or event - test_event1"

    hass.states.async_set(ent1.entity_id, STATE_OFF)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.states.async_set(ent2.entity_id, STATE_ON)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "or event - test_event1"

    hass.states.async_set(ent1.entity_id, STATE_ON)
    hass.bus.async_fire("test_event1")
    await hass.async_block_till_done()
    assert len(calls) == 4
    assert [calls[2].data["some"], calls[3].data["some"]] == unordered(
        ["or event - test_event1", "and event - test_event1"]
    )


async def test_automation_with_bad_sub_condition(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation with bad device condition under and/or conditions."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "event", "event_type": "test_event1"},
                "condition": {
                    "condition": "and",
                    "conditions": [{"condition": "device", "domain": "light"}],
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert "required key not provided" in caplog.text


async def test_automation_with_bad_trigger(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automation with bad device trigger."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {"platform": "device", "domain": "light"},
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    assert "required key not provided" in caplog.text


async def test_websocket_device_not_found(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test calling command with unknown device."""
    await async_setup_component(hass, "device_automation", {})
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "device_automation/action/list", "device_id": "non-existing"}
    )
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert not msg["success"]
    assert msg["error"] == {"code": "not_found", "message": "Device not found"}


async def test_automation_with_unknown_device(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, fake_integration
) -> None:
    """Test device automation with a trigger with an unknown device."""

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_trigger"]
    module.async_validate_trigger_config = AsyncMock()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {
                    "platform": "device",
                    "device_id": "no_such_device",
                    "domain": "fake_integration",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    module.async_validate_trigger_config.assert_not_awaited()
    assert (
        "Automation with alias 'hello' failed to setup triggers and has been disabled: "
        "Unknown device 'no_such_device'" in caplog.text
    )


async def test_automation_with_device_wrong_domain(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
    fake_integration,
) -> None:
    """Test device automation where the device doesn't have the right config entry."""

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_trigger"]
    module.async_validate_trigger_config = AsyncMock()

    device_entry = device_registry.async_get_or_create(
        config_entry_id="not_fake_integration_config_entry",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {
                    "platform": "device",
                    "device_id": device_entry.id,
                    "domain": "fake_integration",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    module.async_validate_trigger_config.assert_not_awaited()
    assert (
        "Automation with alias 'hello' failed to setup triggers and has been disabled: "
        f"Device '{device_entry.id}' has no config entry from domain 'fake_integration'"
        in caplog.text
    )


async def test_automation_with_device_component_not_loaded(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device_registry: dr.DeviceRegistry,
    fake_integration,
) -> None:
    """Test device automation where the device's config entry is not loaded."""

    module_cache = hass.data.setdefault(loader.DATA_COMPONENTS, {})
    module = module_cache["fake_integration.device_trigger"]
    module.async_validate_trigger_config = AsyncMock()
    module.async_attach_trigger = AsyncMock()

    config_entry = MockConfigEntry(domain="fake_integration", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "hello",
                "trigger": {
                    "platform": "device",
                    "device_id": device_entry.id,
                    "domain": "fake_integration",
                },
                "action": {"service": "test.automation", "entity_id": "hello.world"},
            }
        },
    )

    module.async_validate_trigger_config.assert_not_awaited()


@pytest.mark.parametrize(
    "exc",
    [
        IntegrationNotFound("test"),
        RequirementsNotFound("test", []),
        ImportError("test"),
    ],
)
async def test_async_get_device_automations_platform_reraises_exceptions(
    hass: HomeAssistant, exc: Exception
) -> None:
    """Test InvalidDeviceAutomationConfig is raised when async_get_integration_with_requirements fails."""
    await async_setup_component(hass, "device_automation", {})
    with patch(
        "homeassistant.components.device_automation.async_get_integration_with_requirements",
        side_effect=exc,
    ), pytest.raises(InvalidDeviceAutomationConfig):
        await device_automation.async_get_device_automation_platform(
            hass, "test", device_automation.DeviceAutomationType.TRIGGER
        )
