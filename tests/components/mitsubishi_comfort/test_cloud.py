"""Tests for cloud fallback and transport changes."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

from mitsubishi_comfort import CloudIndoorUnit, DeviceInfo
from mitsubishi_comfort.exceptions import (
    AuthenticationError,
    CommandError,
    DeviceConnectionError,
)
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.mitsubishi_comfort.const import CONF_ADDRESSES, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_ADDRESS, MOCK_MAC, MOCK_SERIAL

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("password", "crypto_serial", "mac", "addresses"),
    [
        pytest.param("", "", "", {}, id="new-account"),
        pytest.param("", "0102030405060708090a", MOCK_MAC, {}, id="no-password"),
        pytest.param("dGVzdA==", "", MOCK_MAC, {}, id="no-crypto-serial"),
        pytest.param("dGVzdA==", "0102030405060708090a", "", {}, id="no-mac"),
        pytest.param("dGVzdA==", "0102030405060708090a", MOCK_MAC, {}, id="no-address"),
    ],
)
async def test_cloud_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
    mock_cloud_account: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    password: str,
    crypto_serial: str,
    mac: str,
    addresses: dict[str, str],
) -> None:
    """Missing local data no longer prevents indoor climate entities."""
    mock_cloud_account.discover_devices.return_value = {
        MOCK_SERIAL: replace(
            mock_device_info, password=password, crypto_serial=crypto_serial, mac=mac
        )
    }
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_ADDRESSES: addresses}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert isinstance(
        mock_config_entry.runtime_data[MOCK_SERIAL].device, CloudIndoorUnit
    )
    entity_id = entity_registry.async_get_entity_id(CLIMATE_DOMAIN, DOMAIN, MOCK_SERIAL)
    state = hass.states.get(entity_id)
    assert state.state == "cool"
    assert state.attributes["current_temperature"] == 23.5
    assert "hvac_action" not in state.attributes
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert (dr.CONNECTION_NETWORK_MAC, "") not in device.connections


@pytest.mark.parametrize(
    ("service", "data", "command"),
    [
        pytest.param(
            "set_hvac_mode", {"hvac_mode": "heat"}, {"operationMode": "heat"}, id="mode"
        ),
        pytest.param(
            "set_temperature", {"temperature": 25}, {"spCool": 25.0}, id="temperature"
        ),
        pytest.param(
            "set_fan_mode", {"fan_mode": "auto"}, {"fanSpeed": "auto"}, id="fan"
        ),
        pytest.param(
            "set_swing_mode",
            {"swing_mode": "swing"},
            {"airDirection": "swing"},
            id="vane",
        ),
        pytest.param("turn_off", {}, {"operationMode": "off"}, id="off"),
    ],
)
async def test_cloud_commands(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
    mock_cloud_account: AsyncMock,
    service: str,
    data: dict[str, str | float],
    command: dict[str, str | float],
) -> None:
    """Home Assistant actions use cloud field names without local credentials."""
    mock_device_info.password = ""
    mock_cloud_account.get_device_profile.return_value["hasVaneSwing"] = True
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "climate.living_room", **data},
        blocking=True,
    )
    mock_cloud_account.send_command.assert_awaited_once_with(MOCK_SERIAL, command)


@pytest.mark.parametrize(
    ("error", "reauth_steps"),
    [
        pytest.param(CommandError("rejected"), [], id="rejected"),
        pytest.param(DeviceConnectionError("timeout"), [], id="timeout"),
        pytest.param(
            AuthenticationError("expired"), ["reauth_confirm"], id="authentication"
        ),
    ],
)
async def test_cloud_command_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
    mock_cloud_account: AsyncMock,
    error: Exception,
    reauth_steps: list[str],
) -> None:
    """Failed commands preserve state and only auth failures request reauth."""
    mock_device_info.password = ""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_cloud_account.send_command.side_effect = error
    with pytest.raises(HomeAssistantError, match="did not accept"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            "set_hvac_mode",
            {ATTR_ENTITY_ID: "climate.living_room", "hvac_mode": "heat"},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert hass.states.get("climate.living_room").state == "cool"
    assert [
        (flow["step_id"], flow["context"]["entry_id"])
        for flow in hass.config_entries.flow.async_progress(DOMAIN)
    ] == [(step, mock_config_entry.entry_id) for step in reauth_steps]


@pytest.mark.parametrize(
    ("error", "reauth_steps"),
    [
        pytest.param(DeviceConnectionError("unavailable"), [], id="connection"),
        pytest.param(
            AuthenticationError("expired"), ["reauth_confirm"], id="authentication"
        ),
    ],
)
async def test_mixed_account_cloud_outage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
    error: Exception,
    reauth_steps: list[str],
) -> None:
    """A failed cloud poll does not prevent local devices from loading."""
    account, _ = mock_setup_integration
    account.discover_devices.return_value["CLOUD"] = replace(
        mock_device_info, serial="CLOUD", label="Bedroom", password="", mac=""
    )
    account.get_device_details.side_effect = error
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("climate.living_room").state == "cool"
    assert hass.states.get("climate.bedroom").state == STATE_UNAVAILABLE
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert [
        flow["step_id"] for flow in hass.config_entries.flow.async_progress(DOMAIN)
    ] == reauth_steps

    account.get_device_details.side_effect = None
    await mock_config_entry.runtime_data["CLOUD"].async_refresh()
    assert hass.states.get("climate.bedroom").state == "cool"


@pytest.mark.parametrize(
    ("error", "expected_state", "reauth_steps"),
    [
        pytest.param(
            DeviceConnectionError("unavailable"),
            ConfigEntryState.SETUP_RETRY,
            [],
            id="connection",
        ),
        pytest.param(
            AuthenticationError("expired"),
            ConfigEntryState.SETUP_ERROR,
            ["reauth_confirm"],
            id="authentication",
        ),
    ],
)
async def test_all_devices_fail_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
    error: Exception,
    expected_state: ConfigEntryState,
    reauth_steps: list[str],
) -> None:
    """An account with no working devices fails setup and prioritizes reauth."""
    account, local = mock_setup_integration
    account.discover_devices.return_value["CLOUD"] = replace(
        mock_device_info, serial="CLOUD", label="Bedroom", password="", mac=""
    )
    local.update_status.return_value = False
    account.get_device_details.side_effect = error
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is expected_state
    assert [
        flow["step_id"] for flow in hass.config_entries.flow.async_progress(DOMAIN)
    ] == reauth_steps


async def test_cloud_poll_authentication_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
    mock_cloud_account: AsyncMock,
) -> None:
    """Authentication failure during polling starts reauth without unloading."""
    mock_device_info.password = ""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_cloud_account.get_device_details.side_effect = AuthenticationError("expired")
    await mock_config_entry.runtime_data[MOCK_SERIAL].async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("climate.living_room").state == STATE_UNAVAILABLE
    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_cloud_to_local_preserves_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Learning an address restores local control without replacing the entity."""
    _, local = mock_setup_integration
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_ADDRESSES: {}}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    before = entity_registry.async_get("climate.living_room")
    assert isinstance(
        mock_config_entry.runtime_data[MOCK_SERIAL].device, CloudIndoorUnit
    )

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_ADDRESSES: {dr.format_mac(MOCK_MAC): MOCK_ADDRESS},
        },
    )
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data[MOCK_SERIAL].device is local
    assert entity_registry.async_get("climate.living_room").id == before.id
    assert mock_config_entry.state is ConfigEntryState.LOADED
