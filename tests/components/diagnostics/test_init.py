"""Test the Diagnostics integration."""
from http import HTTPStatus
import json
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.diagnostics import (
    DOMAIN,
    DiagnosticsSubscriptionSupport,
    async_has_subscription,
    async_log_object,
)
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.setup import async_setup_component

from . import _get_diagnostics_for_config_entry, _get_diagnostics_for_device

from tests.common import MockConfigEntry, mock_platform


@pytest.fixture(autouse=True)
async def mock_diagnostics_integration(hass):
    """Mock a diagnostics integration."""
    hass.config.components.add("fake_integration")
    hass.config.components.add("fake_integration_no_subscribe")
    hass.config.components.add("integration_without_diagnostics")
    mock_platform(
        hass,
        "fake_integration.diagnostics",
        Mock(
            async_get_config_entry_diagnostics=AsyncMock(
                return_value={
                    "config_entry": "info",
                }
            ),
            async_get_device_diagnostics=AsyncMock(
                return_value={
                    "device": "info",
                }
            ),
            async_supports_subscription=Mock(
                return_value=DiagnosticsSubscriptionSupport(True, True)
            ),
        ),
    )
    mock_platform(
        hass,
        "fake_integration_no_subscribe.diagnostics",
        Mock(
            async_get_config_entry_diagnostics=AsyncMock(
                return_value={
                    "config_entry": "info",
                }
            ),
            async_get_device_diagnostics=AsyncMock(
                return_value={
                    "device": "info",
                }
            ),
            spec_set=[
                "async_get_config_entry_diagnostics",
                "async_get_device_diagnostics",
            ],
        ),
    )
    mock_platform(
        hass,
        "integration_without_diagnostics.diagnostics",
        Mock(spec_set=[]),
    )
    assert await async_setup_component(hass, DOMAIN, {})


async def test_websocket(hass, hass_ws_client):
    """Test websocket command."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "diagnostics/list"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert len(msg["result"]) == 3
    assert {
        "domain": "fake_integration_no_subscribe",
        "handlers": {"config_entry": True, "device": True},
        "supports_subscription": {"config_entry": False, "domain": False},
    } in msg["result"]
    assert {
        "domain": "fake_integration",
        "handlers": {"config_entry": True, "device": True},
        "supports_subscription": {"config_entry": True, "domain": True},
    } in msg["result"]
    assert {
        "domain": "integration_without_diagnostics",
        "handlers": {"config_entry": False, "device": False},
        "supports_subscription": {"config_entry": False, "domain": False},
    } in msg["result"]

    await client.send_json(
        {"id": 6, "type": "diagnostics/get", "domain": "fake_integration"}
    )

    msg = await client.receive_json()

    assert msg["id"] == 6
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {
        "domain": "fake_integration",
        "handlers": {"config_entry": True, "device": True},
        "supports_subscription": {"config_entry": True, "domain": True},
    }


async def test_download_diagnostics(hass, hass_client):
    """Test download diagnostics."""
    config_entry = MockConfigEntry(domain="fake_integration")
    config_entry.add_to_hass(hass)
    hass_sys_info = await async_get_system_info(hass)
    hass_sys_info["run_as_root"] = hass_sys_info["user"] == "root"
    del hass_sys_info["user"]

    assert await _get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "home_assistant": hass_sys_info,
        "custom_components": {},
        "integration_manifest": {
            "codeowners": [],
            "dependencies": [],
            "domain": "fake_integration",
            "is_built_in": True,
            "name": "fake_integration",
            "requirements": [],
        },
        "data": {"config_entry": "info"},
    }

    dev_reg = async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "test")}
    )

    assert await _get_diagnostics_for_device(
        hass, hass_client, config_entry, device
    ) == {
        "home_assistant": hass_sys_info,
        "custom_components": {},
        "integration_manifest": {
            "codeowners": [],
            "dependencies": [],
            "domain": "fake_integration",
            "is_built_in": True,
            "name": "fake_integration",
            "requirements": [],
        },
        "data": {"device": "info"},
    }


async def test_failure_scenarios(hass, hass_client):
    """Test failure scenarios."""
    client = await hass_client()

    # test wrong d_type
    response = await client.get("/api/diagnostics/wrong_type/fake_id")
    assert response.status == HTTPStatus.BAD_REQUEST

    # test wrong d_id
    response = await client.get("/api/diagnostics/config_entry/fake_id")
    assert response.status == HTTPStatus.NOT_FOUND

    config_entry = MockConfigEntry(domain="integration_without_diagnostics")
    config_entry.add_to_hass(hass)

    # test valid d_type and d_id but no config entry diagnostics
    response = await client.get(
        f"/api/diagnostics/config_entry/{config_entry.entry_id}"
    )
    assert response.status == HTTPStatus.NOT_FOUND

    config_entry = MockConfigEntry(domain="fake_integration")
    config_entry.add_to_hass(hass)

    # test invalid sub_type
    response = await client.get(
        f"/api/diagnostics/config_entry/{config_entry.entry_id}/wrong_type/id"
    )
    assert response.status == HTTPStatus.BAD_REQUEST

    # test invalid sub_id
    response = await client.get(
        f"/api/diagnostics/config_entry/{config_entry.entry_id}/device/fake_id"
    )
    assert response.status == HTTPStatus.NOT_FOUND


async def test_diagnostics_subscription_domain(hass: HomeAssistant, hass_ws_client):
    """Test websocket diagnostics subscription for a domain."""

    client = await hass_ws_client(hass)

    # Test there's no subscription
    assert not async_has_subscription(hass, "fake_integration")

    await client.send_json(
        {"id": 1, "type": "diagnostics/subscribe", "domain": "fake_integration"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert async_has_subscription(hass, "fake_integration")

    # Log some data
    async_log_object(hass, {"some": "data"}, "fake_integration")
    await hass.async_block_till_done()

    response = await client.receive_json()
    assert json.loads(response["event"]) == {"data": {"some": "data"}}

    # Unsubscribe
    await client.send_json({"id": 8, "type": "unsubscribe_events", "subscription": 1})
    response = await client.receive_json()
    assert response["success"]
    assert not async_has_subscription(hass, "fake_integration")
    assert not async_has_subscription(hass, "fake_integration", "fake_config_entry_id")


async def test_diagnostics_subscription_config_entry(
    hass: HomeAssistant, hass_ws_client
):
    """Test websocket diagnostics subscription for a config_entry."""

    client = await hass_ws_client(hass)

    # Test there's no subscription
    assert not async_has_subscription(hass, "fake_integration", "fake_config_entry_id")

    await client.send_json(
        {
            "id": 1,
            "type": "diagnostics/subscribe",
            "domain": "fake_integration",
            "config_entry": "fake_config_entry_id",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert async_has_subscription(hass, "fake_integration", "fake_config_entry_id")

    # Log some data for the domain
    async_log_object(hass, {"some": "data"}, "fake_integration")
    await hass.async_block_till_done()

    response = await client.receive_json()
    assert json.loads(response["event"]) == {"data": {"some": "data"}}

    # Log some data for the config entry
    async_log_object(hass, {"some": "data"}, "fake_integration", "fake_config_entry_id")
    await hass.async_block_till_done()

    response = await client.receive_json()
    assert json.loads(response["event"]) == {"data": {"some": "data"}}

    # Unsubscribe
    await client.send_json({"id": 8, "type": "unsubscribe_events", "subscription": 1})
    response = await client.receive_json()
    assert response["success"]
    assert not async_has_subscription(hass, "fake_integration", "fake_config_entry_id")
