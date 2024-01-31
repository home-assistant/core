"""Test cases for the Shelly component."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from aioshelly.exceptions import (
    DeviceConnectionError,
    FirmwareUnsupported,
    InvalidAuthError,
    MacAddressMismatchError,
)
import pytest

from homeassistant.components.shelly.const import (
    BLOCK_EXPECTED_SLEEP_PERIOD,
    BLOCK_WRONG_SLEEP_PERIOD,
    CONF_BLE_SCANNER_MODE,
    CONF_SLEEP_PERIOD,
    DOMAIN,
    MODELS_WITH_WRONG_SLEEP_PERIOD,
    BLEScannerMode,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.setup import async_setup_component

from . import MOCK_MAC, init_integration, mutate_rpc_device_status

from tests.common import MockConfigEntry


async def test_custom_coap_port(
    hass: HomeAssistant, mock_block_device, caplog: pytest.LogCaptureFixture
) -> None:
    """Test custom coap port."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"coap_port": 7632}},
    )
    await hass.async_block_till_done()

    await init_integration(hass, 1)
    assert "Starting CoAP context with UDP port 7632" in caplog.text


@pytest.mark.parametrize("gen", [1, 2, 3])
async def test_shared_device_mac(
    hass: HomeAssistant,
    gen,
    mock_block_device,
    mock_rpc_device,
    device_reg,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test first time shared device with another domain."""
    config_entry = MockConfigEntry(domain="test", data={}, unique_id="some_id")
    config_entry.add_to_hass(hass)
    device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, format_mac(MOCK_MAC))},
    )
    await init_integration(hass, gen, sleep_period=1000)
    assert "will resume when device is online" in caplog.text


async def test_setup_entry_not_shelly(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test not Shelly entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id) is False
    await hass.async_block_till_done()

    assert "probably comes from a custom integration" in caplog.text


@pytest.mark.parametrize("gen", [1, 2, 3])
@pytest.mark.parametrize("side_effect", [DeviceConnectionError, FirmwareUnsupported])
async def test_device_connection_error(
    hass: HomeAssistant,
    gen,
    side_effect,
    mock_block_device,
    mock_rpc_device,
    monkeypatch,
) -> None:
    """Test device connection error."""
    monkeypatch.setattr(
        mock_block_device, "initialize", AsyncMock(side_effect=side_effect)
    )
    monkeypatch.setattr(
        mock_rpc_device, "initialize", AsyncMock(side_effect=side_effect)
    )

    entry = await init_integration(hass, gen)
    assert entry.state == ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("gen", [1, 2, 3])
async def test_mac_mismatch_error(
    hass: HomeAssistant, gen, mock_block_device, mock_rpc_device, monkeypatch
) -> None:
    """Test device MAC address mismatch error."""
    monkeypatch.setattr(
        mock_block_device, "initialize", AsyncMock(side_effect=MacAddressMismatchError)
    )
    monkeypatch.setattr(
        mock_rpc_device, "initialize", AsyncMock(side_effect=MacAddressMismatchError)
    )

    entry = await init_integration(hass, gen)
    assert entry.state == ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("gen", [1, 2, 3])
async def test_device_auth_error(
    hass: HomeAssistant, gen, mock_block_device, mock_rpc_device, monkeypatch
) -> None:
    """Test device authentication error."""
    monkeypatch.setattr(
        mock_block_device, "initialize", AsyncMock(side_effect=InvalidAuthError)
    )
    monkeypatch.setattr(
        mock_rpc_device, "initialize", AsyncMock(side_effect=InvalidAuthError)
    )

    entry = await init_integration(hass, gen)
    assert entry.state == ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


@pytest.mark.parametrize(("entry_sleep", "device_sleep"), [(None, 0), (1000, 1000)])
async def test_sleeping_block_device_online(
    hass: HomeAssistant,
    entry_sleep,
    device_sleep,
    mock_block_device,
    device_reg,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sleeping block device online."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id="shelly")
    config_entry.add_to_hass(hass)
    device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, format_mac(MOCK_MAC))},
    )

    entry = await init_integration(hass, 1, sleep_period=entry_sleep)
    assert "will resume when device is online" in caplog.text

    mock_block_device.mock_update()
    assert "online, resuming setup" in caplog.text
    assert entry.data["sleep_period"] == device_sleep


@pytest.mark.parametrize(("entry_sleep", "device_sleep"), [(None, 0), (1000, 1000)])
async def test_sleeping_rpc_device_online(
    hass: HomeAssistant,
    entry_sleep,
    device_sleep,
    mock_rpc_device,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sleeping RPC device online."""
    entry = await init_integration(hass, 2, sleep_period=entry_sleep)
    assert "will resume when device is online" in caplog.text

    mock_rpc_device.mock_update()
    assert "online, resuming setup" in caplog.text
    assert entry.data["sleep_period"] == device_sleep


async def test_sleeping_rpc_device_online_new_firmware(
    hass: HomeAssistant,
    mock_rpc_device,
    monkeypatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sleeping device Gen2 with firmware 1.0.0 or later."""
    entry = await init_integration(hass, 2, sleep_period=None)
    assert "will resume when device is online" in caplog.text

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "sys", "wakeup_period", 1500)
    mock_rpc_device.mock_update()
    assert "online, resuming setup" in caplog.text
    assert entry.data["sleep_period"] == 1500


@pytest.mark.parametrize(
    ("gen", "entity_id"),
    [
        (1, "switch.test_name_channel_1"),
        (2, "switch.test_switch_0"),
    ],
)
async def test_entry_unload(
    hass: HomeAssistant, gen, entity_id, mock_block_device, mock_rpc_device
) -> None:
    """Test entry unload."""
    entry = await init_integration(hass, gen)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id).state is STATE_ON

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(entity_id).state is STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("gen", "entity_id"),
    [
        (1, "switch.test_name_channel_1"),
        (2, "switch.test_switch_0"),
    ],
)
async def test_entry_unload_device_not_ready(
    hass: HomeAssistant, gen, entity_id, mock_block_device, mock_rpc_device
) -> None:
    """Test entry unload when device is not ready."""
    entry = await init_integration(hass, gen, sleep_period=1000)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id) is None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_entry_unload_not_connected(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test entry unload when not connected."""
    with patch(
        "homeassistant.components.shelly.coordinator.async_stop_scanner"
    ) as mock_stop_scanner:
        entry = await init_integration(
            hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
        )
        entity_id = "switch.test_switch_0"

        assert entry.state is ConfigEntryState.LOADED
        assert hass.states.get(entity_id).state is STATE_ON
        assert not mock_stop_scanner.call_count

        monkeypatch.setattr(mock_rpc_device, "connected", False)

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert not mock_stop_scanner.call_count
    assert entry.state is ConfigEntryState.LOADED


async def test_entry_unload_not_connected_but_we_think_we_are(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test entry unload when not connected but we think we are still connected."""
    with patch(
        "homeassistant.components.shelly.coordinator.async_stop_scanner",
        side_effect=DeviceConnectionError,
    ) as mock_stop_scanner:
        entry = await init_integration(
            hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
        )
        entity_id = "switch.test_switch_0"

        assert entry.state is ConfigEntryState.LOADED
        assert hass.states.get(entity_id).state is STATE_ON
        assert not mock_stop_scanner.call_count

        monkeypatch.setattr(mock_rpc_device, "connected", False)

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert not mock_stop_scanner.call_count
    assert entry.state is ConfigEntryState.LOADED


async def test_no_attempt_to_stop_scanner_with_sleepy_devices(
    hass: HomeAssistant, mock_rpc_device
) -> None:
    """Test we do not try to stop the scanner if its disabled with a sleepy device."""
    with patch(
        "homeassistant.components.shelly.coordinator.async_stop_scanner",
    ) as mock_stop_scanner:
        entry = await init_integration(hass, 2, sleep_period=7200)
        assert entry.state is ConfigEntryState.LOADED
        assert not mock_stop_scanner.call_count

        mock_rpc_device.mock_update()
        await hass.async_block_till_done()
        assert not mock_stop_scanner.call_count


async def test_entry_missing_gen(hass: HomeAssistant, mock_block_device) -> None:
    """Test successful Gen1 device init when gen is missing in entry data."""
    entry = await init_integration(hass, None)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("switch.test_name_channel_1").state is STATE_ON


@pytest.mark.parametrize(("model"), MODELS_WITH_WRONG_SLEEP_PERIOD)
async def test_sleeping_block_device_wrong_sleep_period(
    hass: HomeAssistant, mock_block_device, model
) -> None:
    """Test sleeping block device with wrong sleep period."""
    entry = await init_integration(
        hass, 1, model=model, sleep_period=BLOCK_WRONG_SLEEP_PERIOD, skip_setup=True
    )
    assert entry.data[CONF_SLEEP_PERIOD] == BLOCK_WRONG_SLEEP_PERIOD
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.data[CONF_SLEEP_PERIOD] == BLOCK_EXPECTED_SLEEP_PERIOD
