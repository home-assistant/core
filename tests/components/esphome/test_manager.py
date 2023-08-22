"""Test ESPHome manager."""
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

from aioesphomeapi import APIClient, DeviceInfo, EntityInfo, EntityState, UserService
import pytest

from homeassistant.components.esphome.const import (
    CONF_DEVICE_NAME,
    DOMAIN,
    STABLE_BLE_VERSION_STR,
)
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


async def test_unique_id_updated_to_mac(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
    """Test we update config entry unique ID to MAC address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="mock-config-name",
    )
    entry.add_to_hass(hass)

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(
            mac_address="1122334455aa",
        )
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == "11:22:33:44:55:aa"


async def test_unique_id_updated_if_name_same_and_already_mac(
    hass: HomeAssistant, mock_client: APIClient, mock_zeroconf: None
) -> None:
    """Test we update config entry unique ID if the name is the same."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455ab", name="test")
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Mac should be updated because name is the same
    assert entry.unique_id == "11:22:33:44:55:ab"


async def test_unique_id_updated_if_name_unset_and_already_mac(
    hass: HomeAssistant, mock_client: APIClient, mock_zeroconf: None
) -> None:
    """Test we update config entry unique ID if the name is unset."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455ab", name="test")
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Mac should be updated because name was unset
    assert entry.unique_id == "11:22:33:44:55:ab"


async def test_unique_id_not_updated_if_name_different_and_already_mac(
    hass: HomeAssistant, mock_client: APIClient, mock_zeroconf: None
) -> None:
    """Test we do not update config entry unique ID if the name is different."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455ab", name="different")
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Mac should not be updated because name is different
    assert entry.unique_id == "11:22:33:44:55:aa"
    # Name should not be updated either
    assert entry.data[CONF_DEVICE_NAME] == "test"


async def test_name_updated_only_if_mac_matches(
    hass: HomeAssistant, mock_client: APIClient, mock_zeroconf: None
) -> None:
    """Test we update config entry name only if the mac matches."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "old",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455aa", name="new")
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == "11:22:33:44:55:aa"
    assert entry.data[CONF_DEVICE_NAME] == "new"


async def test_name_updated_only_if_mac_was_unset(
    hass: HomeAssistant, mock_client: APIClient, mock_zeroconf: None
) -> None:
    """Test we update config entry name if the old unique id was not a mac."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "old",
        },
        unique_id="notamac",
    )
    entry.add_to_hass(hass)

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455aa", name="new")
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == "11:22:33:44:55:aa"
    assert entry.data[CONF_DEVICE_NAME] == "new"


async def test_connection_aborted_wrong_device(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_zeroconf: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we abort the connection if the unique id is a mac and neither name or mac match."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "test.local",
            CONF_PORT: 6053,
            CONF_PASSWORD: "",
            CONF_DEVICE_NAME: "test",
        },
        unique_id="11:22:33:44:55:aa",
    )
    entry.add_to_hass(hass)

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(mac_address="1122334455ab", name="different")
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        "Unexpected device found at test.local; expected `test` "
        "with mac address `11:22:33:44:55:aa`, found `different` "
        "with mac address `11:22:33:44:55:ab`" in caplog.text
    )
