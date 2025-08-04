"""Test repairs for MQTT."""

from collections.abc import Coroutine
from copy import deepcopy
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigSubentry, ConfigSubentryData
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.util.yaml import parse_yaml

from .common import MOCK_NOTIFY_SUBENTRY_DATA_MULTI, async_fire_mqtt_message

from tests.common import MockConfigEntry, async_capture_events
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.conftest import ClientSessionGenerator
from tests.typing import MqttMockHAClientGenerator


async def help_setup_yaml(hass: HomeAssistant, config: dict[str, str]) -> None:
    """Help to set up an exported MQTT device via YAML."""
    with patch(
        "homeassistant.config.load_yaml_config_file",
        return_value=parse_yaml(config["yaml"]),
    ):
        await hass.services.async_call(
            mqtt.DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()


async def help_setup_discovery(hass: HomeAssistant, config: dict[str, str]) -> None:
    """Help to set up an exported MQTT device via YAML."""
    async_fire_mqtt_message(
        hass, config["discovery_topic"], config["discovery_payload"]
    )
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    "mqtt_config_subentries_data",
    [
        (
            ConfigSubentryData(
                data=MOCK_NOTIFY_SUBENTRY_DATA_MULTI,
                subentry_type="device",
                title="Mock subentry",
            ),
        )
    ],
)
@pytest.mark.parametrize(
    ("flow_step", "setup_helper", "translation_key"),
    [
        ("export_yaml", help_setup_yaml, "subentry_migration_yaml"),
        ("export_discovery", help_setup_discovery, "subentry_migration_discovery"),
    ],
)
async def test_subentry_reconfigure_export_settings(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_registry: dr.DeviceRegistry,
    hass_client: ClientSessionGenerator,
    flow_step: str,
    setup_helper: Coroutine[Any, Any, None],
    translation_key: str,
) -> None:
    """Test the subentry ConfigFlow YAML export with migration to YAML."""
    await mqtt_mock_entry()
    config_entry: MockConfigEntry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    subentry_id: str
    subentry: ConfigSubentry
    subentry_id, subentry = next(iter(config_entry.subentries.items()))
    result = await config_entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "summary_menu"

    # assert we have a device for the subentry
    device = device_registry.async_get_device(identifiers={(mqtt.DOMAIN, subentry_id)})
    assert device.config_entries_subentries[config_entry.entry_id] == {subentry_id}
    assert device is not None

    # assert we entity for all subentry components
    components = deepcopy(dict(subentry.data))["components"]
    assert len(components) == 2

    # assert menu options, we have the option to export
    assert result["menu_options"] == [
        "entity",
        "update_entity",
        "delete_entity",
        "device",
        "availability",
        "export",
    ]

    # Open export menu
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": "export"},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "export"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"next_step_id": flow_step},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == flow_step
    assert result["description_placeholders"] == {
        "url": "https://www.home-assistant.io/integrations/mqtt/"
    }

    # Copy the exported config suggested values for an export
    suggested_values_from_schema = {
        field: field.description["suggested_value"]
        for field in result["data_schema"].schema
    }
    #  Try to set up the exported config with a changed device name
    events = async_capture_events(hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)
    await setup_helper(hass, suggested_values_from_schema)

    # Assert the subentry device was not effected by the exported configs
    device = device_registry.async_get_device(identifiers={(mqtt.DOMAIN, subentry_id)})
    assert device.config_entries_subentries[config_entry.entry_id] == {subentry_id}
    assert device is not None

    # Assert a repair flow was created
    # This happens when the exported device identifier was detected
    # The subentry ID is used as device identifier
    assert len(events) == 1
    issue_id = events[0].data["issue_id"]
    issue_registry = ir.async_get(hass)
    repair_issue = issue_registry.async_get_issue(mqtt.DOMAIN, issue_id)
    assert repair_issue.translation_key == translation_key

    await async_process_repairs_platforms(hass)
    client = await hass_client()

    data = await start_repair_fix_flow(client, mqtt.DOMAIN, issue_id)

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"name": "Milk notifier"}
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, flow_id)
    assert data["type"] == "create_entry"

    # Assert the subentry is removed and no other entity has linked the device
    device = device_registry.async_get_device(identifiers={(mqtt.DOMAIN, subentry_id)})
    assert device is None

    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(config_entry.subentries) == 0

    #  Try to set up the exported config again
    events = async_capture_events(hass, ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED)
    await setup_helper(hass, suggested_values_from_schema)
    assert len(events) == 0

    # The MQTT device was now set up from the new source
    await hass.async_block_till_done(wait_background_tasks=True)
    device = device_registry.async_get_device(identifiers={(mqtt.DOMAIN, subentry_id)})
    assert device.config_entries_subentries[config_entry.entry_id] == {None}
    assert device is not None
