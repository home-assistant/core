"""Tests for zeroconf repair issues."""

from unittest.mock import patch

import pytest
from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceInfo

from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.components.zeroconf import DOMAIN, discovery, repairs
from homeassistant.components.zeroconf.discovery import ZEROCONF_TYPE
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import instance_id, issue_registry as ir
from homeassistant.setup import async_setup_component

from .test_init import service_update_mock

from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator


def service_state_change_mock(
    zeroconf,
    services,
    handlers,
    *,
    state_change: ServiceStateChange = ServiceStateChange.Removed,
) -> None:
    """Call service update handler."""
    for service in services:
        handlers[0](zeroconf, service, f"_name.{service}", state_change)


def _get_hass_service_info_mock(
    service_type: str,
    name: str,
    *,
    instance_id="abc123",
) -> AsyncServiceInfo:
    """Return service info for Home Assistant instance."""
    return AsyncServiceInfo(
        ZEROCONF_TYPE,
        name,
        addresses=[b"\n\x00\x00\x01"],
        port=8123,
        weight=0,
        priority=0,
        server="other-host.local.",
        properties={
            "base_url": "http://10.0.0.1:8123",
            "external_url": None,
            "internal_url": "http://10.0.0.1:8123",
            "location_name": "Home",
            "requires_api_password": "True",
            "uuid": instance_id,
            "version": "2025.9.0.dev0",
        },
    )


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_instance_id_conflict_creates_repair_issue_remove(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test that a repair issue is created on instance ID conflict and gets removed when instance disappears."""
    with (
        patch("homeassistant.helpers.instance_id.async_get", return_value="abc123"),
        patch.object(
            discovery, "AsyncServiceBrowser", side_effect=service_update_mock
        ) as mock_browser,
        patch.object(hass.config_entries.flow, "async_init"),
        patch(
            "homeassistant.components.zeroconf.discovery.AsyncServiceInfo",
            side_effect=_get_hass_service_info_mock,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        issue = issue_registry.async_get_issue(
            domain="zeroconf", issue_id="duplicate_instance_id"
        )
        assert issue
        assert issue.severity == ir.IssueSeverity.ERROR
        assert issue.translation_key == "duplicate_instance_id"
        assert issue.translation_placeholders == {
            "other_host_url": "other-host.local",
            "other_ip": "10.0.0.1",
            "instance_id": "abc123",
        }

        # Now test that the issue is removed when the service goes away
        service_state_change_mock(
            mock_browser.call_args[0][0],
            [ZEROCONF_TYPE],
            mock_browser.call_args[1]["handlers"],
        )
        assert (
            issue_registry.async_get_issue(
                domain="zeroconf", issue_id="duplicate_instance_id"
            )
            is None
        )


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_instance_id_conflict_creates_repair_issue_changing_id(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test that a repair issue is created on instance ID conflict and gets removed when instance ID changes."""
    with (
        patch("homeassistant.helpers.instance_id.async_get", return_value="abc123"),
        patch.object(
            discovery, "AsyncServiceBrowser", side_effect=service_update_mock
        ) as mock_browser,
        patch.object(hass.config_entries.flow, "async_init"),
        patch(
            "homeassistant.components.zeroconf.discovery.AsyncServiceInfo",
            side_effect=_get_hass_service_info_mock,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        issue = issue_registry.async_get_issue(
            domain="zeroconf", issue_id="duplicate_instance_id"
        )
        assert issue
        assert issue.severity == ir.IssueSeverity.ERROR
        assert issue.translation_key == "duplicate_instance_id"
        assert issue.translation_placeholders == {
            "other_host_url": "other-host.local",
            "other_ip": "10.0.0.1",
            "instance_id": "abc123",
        }

        with (
            patch(
                "homeassistant.components.zeroconf.discovery.AsyncServiceInfo",
                side_effect=lambda service_type, name: _get_hass_service_info_mock(
                    service_type, name, instance_id="different-id"
                ),
            ),
        ):
            # Now test that the issue is removed when the service goes away
            service_state_change_mock(
                mock_browser.call_args[0][0],
                [ZEROCONF_TYPE],
                mock_browser.call_args[1]["handlers"],
                state_change=ServiceStateChange.Updated,
            )
            assert (
                issue_registry.async_get_issue(
                    domain="zeroconf", issue_id="duplicate_instance_id"
                )
                is None
            )


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_instance_id_no_repair_issue_own_ip(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test that no repair issue is created when the other instance ID matches our IP."""
    with (
        patch("homeassistant.helpers.instance_id.async_get", return_value="abc123"),
        patch.object(discovery, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch.object(hass.config_entries.flow, "async_init"),
        patch(
            "homeassistant.components.zeroconf.discovery.AsyncServiceInfo",
            side_effect=_get_hass_service_info_mock,
        ),
        patch(
            "homeassistant.components.network.async_get_announce_addresses",
            return_value=["10.0.0.1", "10.0.0.2"],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert (
            issue_registry.async_get_issue(
                domain="zeroconf", issue_id="duplicate_instance_id"
            )
            is None
        )


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_instance_id_no_conflict_no_repair_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test that a repair issue is not created when no instance ID conflict exists."""
    with (
        patch("homeassistant.helpers.instance_id.async_get", return_value="xyz123"),
        patch.object(discovery, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch.object(hass.config_entries.flow, "async_init"),
        patch(
            "homeassistant.components.zeroconf.discovery.AsyncServiceInfo",
            side_effect=_get_hass_service_info_mock,
        ),
        patch("homeassistant.helpers.issue_registry.async_create_issue"),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        assert (
            issue_registry.async_get_issue(
                domain="zeroconf", issue_id="duplicate_instance_id"
            )
            is None
        )


async def test_create_fix_flow_raises_on_unknown_issue_id(hass: HomeAssistant) -> None:
    """Test create_fix_flow raises on unknown issue_id."""

    with pytest.raises(ValueError):
        await repairs.async_create_fix_flow(hass, "no_such_issue", None)


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_duplicate_repair_issue_repair_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test desired flow of the fix flow for duplicate instance ID."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})
    assert await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    await async_process_repairs_platforms(hass)

    with (
        patch("homeassistant.helpers.instance_id.async_get", return_value="abc123"),
        patch.object(discovery, "AsyncServiceBrowser", side_effect=service_update_mock),
        patch.object(hass.config_entries.flow, "async_init"),
        patch(
            "homeassistant.components.zeroconf.discovery.AsyncServiceInfo",
            side_effect=_get_hass_service_info_mock,
        ),
        patch.object(
            instance_id, "async_recreate", return_value="new-uuid"
        ) as mock_recreate,
        patch("homeassistant.config.async_check_ha_config_file", return_value=None),
        patch("homeassistant.core.HomeAssistant.async_stop", return_value=None),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        issue = issue_registry.async_get_issue(
            domain="zeroconf", issue_id="duplicate_instance_id"
        )
        assert issue is not None

        client = await hass_client()

        result = await start_repair_fix_flow(client, DOMAIN, issue.issue_id)

        flow_id = result["flow_id"]
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm_recreate"

        result = await process_repair_fix_flow(client, flow_id, json={})
        assert result["type"] == "create_entry"

        await hass.async_block_till_done()

        assert mock_recreate.called
