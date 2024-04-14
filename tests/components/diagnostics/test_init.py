"""Test the Diagnostics integration."""

from http import HTTPStatus
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.setup import async_setup_component

from . import _get_diagnostics_for_config_entry, _get_diagnostics_for_device

from tests.common import MockConfigEntry, mock_platform
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture(autouse=True)
async def mock_diagnostics_integration(hass):
    """Mock a diagnostics integration."""
    hass.config.components.add("fake_integration")
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
        ),
    )
    mock_platform(
        hass,
        "integration_without_diagnostics.diagnostics",
        Mock(),
    )
    assert await async_setup_component(hass, "diagnostics", {})


async def test_websocket(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test websocket command."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "diagnostics/list"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == [
        {
            "domain": "fake_integration",
            "handlers": {"config_entry": True, "device": True},
        }
    ]

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
    }


async def test_download_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    enable_custom_integrations: None,
) -> None:
    """Test download diagnostics."""
    config_entry = MockConfigEntry(domain="fake_integration")
    config_entry.add_to_hass(hass)
    hass_sys_info = await async_get_system_info(hass)
    hass_sys_info["run_as_root"] = hass_sys_info["user"] == "root"
    del hass_sys_info["user"]

    assert await _get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "home_assistant": hass_sys_info,
        "custom_components": {
            "test": {
                "documentation": "http://example.com",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_blocked_version": {
                "documentation": None,
                "requirements": [],
                "version": "1.0.0",
            },
            "test_embedded": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_integration_frame": {
                "documentation": "http://example.com",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_integration_platform": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_legacy_state_translations": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_legacy_state_translations_bad_data": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_package": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_package_loaded_executor": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_package_loaded_loop": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_package_raises_cancelled_error": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_package_raises_cancelled_error_config_entry": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_with_services": {
                "documentation": None,
                "requirements": [],
                "version": "1.0",
            },
        },
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
        "custom_components": {
            "test": {
                "documentation": "http://example.com",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_blocked_version": {
                "documentation": None,
                "requirements": [],
                "version": "1.0.0",
            },
            "test_embedded": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_integration_frame": {
                "documentation": "http://example.com",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_integration_platform": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_legacy_state_translations": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_legacy_state_translations_bad_data": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_package": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_package_loaded_executor": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_package_loaded_loop": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_package_raises_cancelled_error": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_package_raises_cancelled_error_config_entry": {
                "documentation": "http://test-package.io",
                "requirements": [],
                "version": "1.2.3",
            },
            "test_with_services": {
                "documentation": None,
                "requirements": [],
                "version": "1.0",
            },
        },
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


async def test_failure_scenarios(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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
