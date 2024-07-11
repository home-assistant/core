"""Test cases for the Shelly component."""

from ipaddress import IPv4Address
from unittest.mock import AsyncMock, Mock, call, patch

from aioshelly.block_device import COAP
from aioshelly.common import ConnectionOptions
from aioshelly.const import MODEL_PLUS_2PM
from aioshelly.exceptions import (
    DeviceConnectionError,
    InvalidAuthError,
    MacAddressMismatchError,
)
import pytest

from homeassistant.components.shelly.const import (
    BLOCK_EXPECTED_SLEEP_PERIOD,
    BLOCK_WRONG_SLEEP_PERIOD,
    CONF_BLE_SCANNER_MODE,
    CONF_GEN,
    CONF_SLEEP_PERIOD,
    DOMAIN,
    MODELS_WITH_WRONG_SLEEP_PERIOD,
    BLEScannerMode,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceRegistry,
    format_mac,
)
from homeassistant.setup import async_setup_component

from . import MOCK_MAC, init_integration, mutate_rpc_device_status

from tests.common import MockConfigEntry


async def test_custom_coap_port(
    hass: HomeAssistant, mock_block_device: Mock, caplog: pytest.LogCaptureFixture
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


async def test_ip_address_with_only_default_interface(
    hass: HomeAssistant, mock_block_device: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test more local ip addresses with only the default interface.."""
    with (
        patch(
            "homeassistant.components.network.async_only_default_interface_enabled",
            return_value=True,
        ),
        patch(
            "homeassistant.components.network.async_get_enabled_source_ips",
            return_value=[IPv4Address("192.168.1.10"), IPv4Address("10.10.10.10")],
        ),
        patch(
            "homeassistant.components.shelly.utils.COAP",
            autospec=COAP,
        ) as mock_coap_init,
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"coap_port": 7632}})
        await hass.async_block_till_done()

        await init_integration(hass, 1)
        assert "Starting CoAP context with UDP port 7632" in caplog.text
        # Make sure COAP.initialize is called with an empty list
        # when async_only_default_interface_enabled is True even if
        # async_get_enabled_source_ips returns more than one address
        assert mock_coap_init.mock_calls[1] == call().initialize(7632, [])


async def test_ip_address_without_only_default_interface(
    hass: HomeAssistant, mock_block_device: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test more local ip addresses without only the default interface.."""
    with (
        patch(
            "homeassistant.components.network.async_only_default_interface_enabled",
            return_value=False,
        ),
        patch(
            "homeassistant.components.network.async_get_enabled_source_ips",
            return_value=[IPv4Address("192.168.1.10"), IPv4Address("10.10.10.10")],
        ),
        patch(
            "homeassistant.components.shelly.utils.COAP",
            autospec=COAP,
        ) as mock_coap_init,
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"coap_port": 7632}})
        await hass.async_block_till_done()

        await init_integration(hass, 1)
        assert "Starting CoAP context with UDP port 7632" in caplog.text
        assert mock_coap_init.mock_calls[1] == call().initialize(
            7632, [IPv4Address("192.168.1.10"), IPv4Address("10.10.10.10")]
        )


@pytest.mark.parametrize("gen", [1, 2, 3])
async def test_shared_device_mac(
    hass: HomeAssistant,
    gen: int,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    device_registry: DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test first time shared device with another domain."""
    config_entry = MockConfigEntry(domain="test", data={}, unique_id="some_id")
    config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
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
async def test_device_connection_error(
    hass: HomeAssistant,
    gen: int,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test device connection error."""
    monkeypatch.setattr(
        mock_block_device, "initialize", AsyncMock(side_effect=DeviceConnectionError)
    )
    monkeypatch.setattr(
        mock_rpc_device, "initialize", AsyncMock(side_effect=DeviceConnectionError)
    )

    entry = await init_integration(hass, gen)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("gen", [1, 2, 3])
async def test_device_unsupported_firmware(
    hass: HomeAssistant,
    gen: int,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test device init with unsupported firmware."""
    monkeypatch.setattr(mock_block_device, "firmware_supported", False)
    monkeypatch.setattr(mock_rpc_device, "firmware_supported", False)

    entry = await init_integration(hass, gen)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        DOMAIN,
        "firmware_unsupported_123456789ABC",
    ) in issue_registry.issues


@pytest.mark.parametrize("gen", [1, 2, 3])
async def test_mac_mismatch_error(
    hass: HomeAssistant,
    gen: int,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test device MAC address mismatch error."""
    monkeypatch.setattr(
        mock_block_device, "initialize", AsyncMock(side_effect=MacAddressMismatchError)
    )
    monkeypatch.setattr(
        mock_rpc_device, "initialize", AsyncMock(side_effect=MacAddressMismatchError)
    )

    entry = await init_integration(hass, gen)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("gen", [1, 2, 3])
async def test_device_auth_error(
    hass: HomeAssistant,
    gen: int,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test device authentication error."""
    monkeypatch.setattr(
        mock_block_device, "initialize", AsyncMock(side_effect=InvalidAuthError)
    )
    monkeypatch.setattr(
        mock_rpc_device, "initialize", AsyncMock(side_effect=InvalidAuthError)
    )

    entry = await init_integration(hass, gen)
    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


@pytest.mark.parametrize(("entry_sleep", "device_sleep"), [(None, 0), (3600, 3600)])
async def test_sleeping_block_device_online(
    hass: HomeAssistant,
    entry_sleep: int | None,
    device_sleep: int,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    device_registry: DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sleeping block device online."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id="shelly")
    config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, format_mac(MOCK_MAC))},
    )

    monkeypatch.setitem(
        mock_block_device.settings,
        "sleep_mode",
        {"period": int(device_sleep / 60), "unit": "m"},
    )
    entry = await init_integration(hass, 1, sleep_period=entry_sleep)
    assert "will resume when device is online" in caplog.text

    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "online, resuming setup" in caplog.text
    assert entry.data["sleep_period"] == device_sleep


@pytest.mark.parametrize(("entry_sleep", "device_sleep"), [(None, 0), (1000, 1000)])
async def test_sleeping_rpc_device_online(
    hass: HomeAssistant,
    entry_sleep: int | None,
    device_sleep: int,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sleeping RPC device online."""
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", device_sleep)
    entry = await init_integration(hass, 2, sleep_period=entry_sleep)
    assert "will resume when device is online" in caplog.text

    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "online, resuming setup" in caplog.text
    assert entry.data["sleep_period"] == device_sleep


async def test_sleeping_rpc_device_online_new_firmware(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sleeping device Gen2 with firmware 1.0.0 or later."""
    entry = await init_integration(hass, 2, sleep_period=None)
    assert "will resume when device is online" in caplog.text

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "sys", "wakeup_period", 1500)
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

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
    hass: HomeAssistant,
    gen: int,
    entity_id: str,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
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
    hass: HomeAssistant,
    gen: int,
    entity_id: str,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
) -> None:
    """Test entry unload when device is not ready."""
    entry = await init_integration(hass, gen, sleep_period=1000)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id) is None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_entry_unload_not_connected(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
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
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
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
    hass: HomeAssistant, mock_rpc_device: Mock
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


async def test_entry_missing_gen(hass: HomeAssistant, mock_block_device: Mock) -> None:
    """Test successful Gen1 device init when gen is missing in entry data."""
    entry = await init_integration(hass, None)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("switch.test_name_channel_1").state is STATE_ON


async def test_entry_missing_port(hass: HomeAssistant) -> None:
    """Test successful Gen2 device init when port is missing in entry data."""
    data = {
        CONF_HOST: "192.168.1.37",
        CONF_SLEEP_PERIOD: 0,
        "model": MODEL_PLUS_2PM,
        CONF_GEN: 2,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.shelly.RpcDevice.initialize"),
        patch(
            "homeassistant.components.shelly.RpcDevice.create", return_value=Mock()
        ) as rpc_device_mock,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert rpc_device_mock.call_args[0][2] == ConnectionOptions(
            ip_address="192.168.1.37", device_mac="123456789ABC", port=80
        )


async def test_rpc_entry_custom_port(hass: HomeAssistant) -> None:
    """Test successful Gen2 device init using custom port."""
    data = {
        CONF_HOST: "192.168.1.37",
        CONF_SLEEP_PERIOD: 0,
        "model": MODEL_PLUS_2PM,
        CONF_GEN: 2,
        CONF_PORT: 8001,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id=MOCK_MAC)
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.shelly.RpcDevice.initialize"),
        patch(
            "homeassistant.components.shelly.RpcDevice.create", return_value=Mock()
        ) as rpc_device_mock,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert rpc_device_mock.call_args[0][2] == ConnectionOptions(
            ip_address="192.168.1.37", device_mac="123456789ABC", port=8001
        )


@pytest.mark.parametrize(("model"), MODELS_WITH_WRONG_SLEEP_PERIOD)
async def test_sleeping_block_device_wrong_sleep_period(
    hass: HomeAssistant, mock_block_device: Mock, model: str
) -> None:
    """Test sleeping block device with wrong sleep period."""
    entry = await init_integration(
        hass, 1, model=model, sleep_period=BLOCK_WRONG_SLEEP_PERIOD, skip_setup=True
    )
    assert entry.data[CONF_SLEEP_PERIOD] == BLOCK_WRONG_SLEEP_PERIOD
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.data[CONF_SLEEP_PERIOD] == BLOCK_EXPECTED_SLEEP_PERIOD
