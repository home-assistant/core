"""Test ESPHome manager."""
from collections.abc import Awaitable, Callable

from aioesphomeapi import APIClient, EntityInfo, EntityState, UserService

from homeassistant.components.esphome.const import DOMAIN, STABLE_BLE_VERSION_STR
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .conftest import MockESPHomeDevice

from tests.common import MockConfigEntry


async def test_esphome_device_with_old_bluetooth(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a device with old bluetooth creates an issue."""
    entity_info = []
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        device_info={"bluetooth_proxy_feature_flags": 1, "esphome_version": "2023.3.0"},
    )
    await hass.async_block_till_done()
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        "esphome", "ble_firmware_outdated-11:22:33:44:55:aa"
    )
    assert (
        issue.learn_more_url
        == f"https://esphome.io/changelog/{STABLE_BLE_VERSION_STR}.html"
    )


async def test_esphome_device_with_password(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a device with legacy password creates an issue."""
    entity_info = []
    states = []
    user_service = []

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "has",
        },
    )
    entry.add_to_hass(hass)
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        device_info={"bluetooth_proxy_feature_flags": 0, "esphome_version": "2023.3.0"},
        entry=entry,
    )
    await hass.async_block_till_done()
    issue_registry = ir.async_get(hass)
    assert (
        issue_registry.async_get_issue(
            "esphome", "api_password_deprecated-11:22:33:44:55:aa"
        )
        is not None
    )


async def test_esphome_device_with_current_bluetooth(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a device with recent bluetooth does not create an issue."""
    entity_info = []
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
        device_info={
            "bluetooth_proxy_feature_flags": 1,
            "esphome_version": STABLE_BLE_VERSION_STR,
        },
    )
    await hass.async_block_till_done()
    issue_registry = ir.async_get(hass)
    assert (
        issue_registry.async_get_issue(
            "esphome", "ble_firmware_outdated-11:22:33:44:55:aa"
        )
        is None
    )
