"""Test the Diagnostics integration."""

from datetime import datetime
from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import attr
from freezegun import freeze_time
import pytest

from homeassistant.components.diagnostics import _DIAGNOSTICS_DATA, DOMAIN
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from . import _get_diagnostics_for_config_entry, _get_diagnostics_for_device

from tests.common import MockConfigEntry, mock_platform
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture(autouse=True)
async def mock_diagnostics_integration(hass: HomeAssistant) -> None:
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
    assert await async_setup_component(hass, DOMAIN, {})


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


@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.parametrize(
    "ignore_missing_translations",
    [
        [
            "component.fake_integration.issues.test_issue.title",
            "component.fake_integration.issues.test_issue.description",
        ]
    ],
)
async def test_download_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test download diagnostics."""
    config_entry = MockConfigEntry(domain="fake_integration")
    config_entry.add_to_hass(hass)
    hass_sys_info = await async_get_system_info(hass)
    hass_sys_info["run_as_root"] = hass_sys_info["user"] == "root"
    del hass_sys_info["user"]
    integration = await async_get_integration(hass, "fake_integration")
    original_manifest = integration.manifest.copy()
    original_manifest["codeowners"] = ["@test"]

    with freeze_time(datetime(2025, 7, 9, 14, 00, 00)):
        issue_registry.async_get_or_create(
            domain="fake_integration",
            issue_id="test_issue",
            breaks_in_ha_version="2023.10.0",
            severity=ir.IssueSeverity.WARNING,
            is_fixable=False,
            is_persistent=True,
            translation_key="test_issue",
        )

    with patch.object(integration, "manifest", original_manifest):
        response = await _get_diagnostics_for_config_entry(
            hass, hass_client, config_entry
        )
    assert response == {
        "home_assistant": hass_sys_info,
        "setup_times": {},
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
            "codeowners": ["test"],
            "dependencies": [],
            "domain": "fake_integration",
            "integration_type": "hub",
            "is_built_in": True,
            "overwrites_built_in": False,
            "name": "fake_integration",
            "requirements": [],
        },
        "data": {"config_entry": "info"},
        "issues": [
            {
                "breaks_in_ha_version": "2023.10.0",
                "created": "2025-07-09T14:00:00+00:00",
                "data": None,
                "dismissed_version": None,
                "domain": "fake_integration",
                "is_fixable": False,
                "is_persistent": True,
                "issue_domain": None,
                "issue_id": "test_issue",
                "learn_more_url": None,
                "severity": "warning",
                "translation_key": "test_issue",
                "translation_placeholders": None,
            },
        ],
    }

    device = device_registry.async_get_or_create(
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
            "integration_type": "hub",
            "is_built_in": True,
            "overwrites_built_in": False,
            "name": "fake_integration",
            "requirements": [],
        },
        "data": {"device": "info"},
        "issues": [
            {
                "breaks_in_ha_version": "2023.10.0",
                "created": "2025-07-09T14:00:00+00:00",
                "data": None,
                "dismissed_version": None,
                "domain": "fake_integration",
                "is_fixable": False,
                "is_persistent": True,
                "issue_domain": None,
                "issue_id": "test_issue",
                "learn_more_url": None,
                "severity": "warning",
                "translation_key": "test_issue",
                "translation_placeholders": None,
            },
        ],
        "setup_times": {},
    }


async def test_download_diagnostics_requires_admin(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test diagnostics download is restricted to admin users."""
    config_entry = MockConfigEntry(domain="fake_integration")
    config_entry.add_to_hass(hass)

    client = await hass_client(hass_read_only_access_token)
    response = await client.get(
        f"/api/diagnostics/config_entry/{config_entry.entry_id}"
    )
    assert response.status == HTTPStatus.UNAUTHORIZED


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


@pytest.mark.parametrize(
    "device_key",
    [
        pytest.param("parent", id="main_device"),
        pytest.param("child", id="child_device"),
    ],
)
async def test_download_diagnostics_device_not_owned_by_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    device_key: str,
) -> None:
    """Test requesting device diagnostics via a config entry that doesn't own it.

    A device (main or child) belonging to another config entry must be rejected
    with a not-found response, never handed to the URL entry's integration.
    """
    owner_entry = MockConfigEntry(domain="fake_integration")
    owner_entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain="fake_integration")
    other_entry.add_to_hass(hass)

    parent = device_registry.async_get_or_create(
        config_entry_id=owner_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    child = device_registry.async_get_or_create_child(
        config_entry_id=owner_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    devices = {"parent": parent, "child": child}

    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{other_entry.entry_id}"
        f"/device/{devices[device_key].id}"
    )
    assert response.status == HTTPStatus.NOT_FOUND


async def test_download_diagnostics_composite_device_rejected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test requesting device diagnostics for a pre-migration composite device.

    A composite device id spans multiple config entries and has no single owner,
    so it must be rejected with a not-found response and never handed to the
    integration's device diagnostics handler.
    """
    entry_1 = MockConfigEntry(domain="fake_integration")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="fake_integration")
    entry_2.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "1")}
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "2")}
    )
    composite_id = "composite00000000000000000000ab"
    # Simulate a migration split: both devices carry the pre-migration composite id
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=composite_id
    )
    device_registry._devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=composite_id
    )
    # Check the device is a composite device id, which is not supported for diagnostics
    assert device_registry.async_get(composite_id) is not None
    assert (
        device_registry.async_get(composite_id, include_composite_devices=False) is None
    )

    handler = (
        hass.data[_DIAGNOSTICS_DATA].platforms["fake_integration"].device_diagnostics
    )

    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{entry_1.entry_id}/device/{composite_id}"
    )
    assert response.status == HTTPStatus.NOT_FOUND
    handler.assert_not_called()
