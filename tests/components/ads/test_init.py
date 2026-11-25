"""Test the ADS component setup."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pyads
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.ads.const import DOMAIN
from homeassistant.components.ads.entity import AdsEntity
from homeassistant.components.ads.switch import AdsSwitch
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_DEVICE,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import ADS_CONFIG, MockAdsDevice, get_hub, setup_ads_platform
from .const import AMS_NET_ID, IP_ADDRESS, PORT

SWITCH_VAR = "GVL.pump"
SWITCH_ID = "switch.pump"
SWITCH_CONFIG = {"adsvar": SWITCH_VAR, "name": "Pump"}


@pytest.mark.parametrize(
    ("config", "expected_args"),
    [
        pytest.param(ADS_CONFIG, (AMS_NET_ID, PORT, IP_ADDRESS), id="ip_address"),
        pytest.param(
            {"device": AMS_NET_ID, "port": PORT},
            (AMS_NET_ID, PORT, None),
            id="no_ip_address",
        ),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    config: dict[str, Any],
    expected_args: tuple[str, int, str | None],
) -> None:
    """Test the component opens the connection it was configured with."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()

    mock_pyads_connection.assert_called_once_with(*expected_args)
    mock_pyads_connection.return_value.open.assert_called_once()


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"port": PORT}, id="missing_device"),
        pytest.param({"device": AMS_NET_ID}, id="missing_port"),
        pytest.param({"device": AMS_NET_ID, "port": 70000}, id="invalid_port"),
    ],
)
async def test_invalid_config(
    hass: HomeAssistant, mock_pyads_connection: MagicMock, config: dict[str, Any]
) -> None:
    """Test an invalid configuration never opens a connection."""
    assert not await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()

    mock_pyads_connection.assert_not_called()


async def test_setup_without_ads_section(
    hass: HomeAssistant, mock_pyads_connection: MagicMock
) -> None:
    """Test the component sets up without a connection when YAML has none."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    mock_pyads_connection.assert_not_called()


async def test_setup_connection_error(
    hass: HomeAssistant, mock_pyads_connection: MagicMock
) -> None:
    """Test an imported connection the device refuses is retried."""
    mock_pyads_connection.return_value.open.side_effect = pyads.ADSError(err_code=1861)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: ADS_CONFIG})
    await hass.async_block_till_done()

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    # The action is registered regardless of the connection.
    assert hass.services.has_service(DOMAIN, "write_data_by_name")


@pytest.mark.usefixtures("setup_ads")
async def test_shutdown_on_stop(
    hass: HomeAssistant, mock_pyads_connection: MagicMock
) -> None:
    """Test the connection is closed when Home Assistant stops."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_pyads_connection.return_value.close.assert_called_once()


@pytest.mark.usefixtures("setup_ads")
async def test_shutdown_close_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failure to close the connection is logged, not raised."""
    mock_pyads_connection.return_value.close.side_effect = pyads.ADSError(err_code=1864)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert "ads-port not opened (1864)" in caplog.text


async def test_shutdown_deletes_the_notifications(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test stopping deletes every notification before closing the connection."""
    mock_ads_device.values["GVL.temperature"] = b"\x00\x00"
    assert await setup_ads_platform(
        hass, mock_ads_device, SENSOR_DOMAIN, {"adsvar": "GVL.temperature"}
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    client = mock_pyads_connection.return_value
    client.del_device_notification.assert_called_once_with(1, 1)
    assert client.mock_calls.index(call.del_device_notification(1, 1)) < (
        client.mock_calls.index(call.close())
    )


async def test_shutdown_notification_delete_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a notification that cannot be deleted still lets the connection close."""
    mock_ads_device.values["GVL.temperature"] = b"\x00\x00"
    assert await setup_ads_platform(
        hass, mock_ads_device, SENSOR_DOMAIN, {"adsvar": "GVL.temperature"}
    )
    client = mock_pyads_connection.return_value
    client.del_device_notification.side_effect = pyads.ADSError(err_code=1861)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert "timeout elapsed (1861)" in caplog.text
    client.close.assert_called_once()


async def test_notification_for_an_unknown_handle(
    hass: HomeAssistant,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a notification nobody subscribed to is logged and dropped."""
    mock_ads_device.values["GVL.temperature"] = b"\x00\x00"
    assert await setup_ads_platform(
        hass, mock_ads_device, SENSOR_DOMAIN, {"adsvar": "GVL.temperature"}
    )

    await mock_ads_device.async_push_unknown(hass, b"\x00\x00")

    assert "Unknown device notification handle: 2" in caplog.text


@pytest.mark.usefixtures("mock_pyads_connection")
async def test_yaml_import(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the YAML connection is imported and a deprecation issue raised."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: ADS_CONFIG})
    await hass.async_block_till_done()

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data == ADS_CONFIG
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue.severity is ir.IssueSeverity.WARNING


@pytest.mark.usefixtures("mock_pyads_connection")
async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the YAML block is still flagged for removal once an entry exists."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: ADS_CONFIG})
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")


async def test_yaml_import_invalid_net_id(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a failed import raises an error issue instead of the deprecation."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {**ADS_CONFIG, CONF_DEVICE: "bad"}}
    )
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_net_id"
    )
    # The connection stays down until the user acts, so this is not a notice.
    assert issue.severity is ir.IssueSeverity.ERROR
    assert not issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")


async def test_yaml_import_device_offline(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a device offline at import still gets an entry that retries setup.

    The YAML entities then come up as soon as the device answers, instead of
    waiting for the user to restart Home Assistant.
    """
    client = mock_pyads_connection.return_value
    client.read_state.side_effect = pyads.ADSError(err_code=1861)
    mock_ads_device.values[SWITCH_VAR] = b"\x01"

    assert await setup_ads_platform(hass, mock_ads_device, SWITCH_DOMAIN, SWITCH_CONFIG)

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get(SWITCH_ID) is None
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")

    client.read_state.side_effect = None
    client.read_state.return_value = (pyads.ADSSTATE_RUN, 0)
    # The entry retries first; the platform then retries on its own timer.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done(wait_background_tasks=True)
    for delivery in mock_ads_device.deliveries:
        await hass.async_add_executor_job(delivery.join)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_ID).state == STATE_ON


async def test_setup_device_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
    mock_create_connection: MagicMock,
) -> None:
    """Test an unreachable device fails setup at once, without pyads.

    The AMS router would otherwise keep retrying the TCP connection for
    minutes before the first request returned.
    """
    mock_create_connection.side_effect = TimeoutError("timed out")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_create_connection.assert_called_once_with((IP_ADDRESS, 48898), timeout=5)
    mock_pyads_connection.assert_not_called()


async def test_setup_derives_address_from_net_id(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_create_connection: MagicMock,
) -> None:
    """Test the reachability check uses the address pyads derives from the NetID."""
    entry = MockConfigEntry(
        domain=DOMAIN, title=AMS_NET_ID, data={"device": AMS_NET_ID, "port": PORT}
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    host = ".".join(AMS_NET_ID.split(".")[:4])
    mock_create_connection.assert_called_once_with((host, 48898), timeout=5)


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test setting up the entry opens the connection and unloading closes it."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    client = mock_pyads_connection.return_value
    client.open.assert_called_once()
    client.read_state.assert_called_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    client.close.assert_called_once()


@pytest.mark.parametrize(
    "configure_mock",
    [
        pytest.param(
            lambda mock: setattr(
                mock.return_value.read_state,
                "side_effect",
                pyads.ADSError(err_code=1861),
            ),
            id="timeout",
        ),
        pytest.param(
            lambda mock: setattr(
                mock.return_value.open,
                "side_effect",
                RuntimeError("Failed to open port on AMS router."),
            ),
            id="router_down",
        ),
    ],
)
async def test_setup_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
    configure_mock: Callable[[MagicMock], None],
) -> None:
    """Test the entry is retried while the device or the router is unreachable."""
    configure_mock(mock_pyads_connection)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_reload_resubscribes_yaml_entities(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test a YAML entity goes unavailable on unload and follows the PLC after a reload."""
    mock_ads_device.values[SWITCH_VAR] = b"\x01"
    assert await setup_ads_platform(hass, mock_ads_device, SWITCH_DOMAIN, SWITCH_CONFIG)
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    old_hub = get_hub(hass)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH_ID).state == STATE_UNAVAILABLE

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert get_hub(hass) is not old_hub
    assert mock_pyads_connection.return_value.add_device_notification.call_count == 2
    assert hass.states.get(SWITCH_ID).state == STATE_ON
    await mock_ads_device.async_push(hass, SWITCH_VAR, b"\x00")
    assert hass.states.get(SWITCH_ID).state == STATE_OFF


async def test_entity_removed_while_unloaded_is_not_resubscribed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test an entity removed while the entry is unloaded stays gone."""
    mock_ads_device.values[SWITCH_VAR] = b"\x01"
    assert await setup_ads_platform(hass, mock_ads_device, SWITCH_DOMAIN, SWITCH_CONFIG)
    (entry,) = hass.config_entries.async_entries(DOMAIN)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    entity_registry.async_remove(SWITCH_ID)
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert not get_hub(hass).devices
    mock_pyads_connection.return_value.add_device_notification.assert_called_once()


async def test_reload_resubscribe_error_is_contained(
    hass: HomeAssistant,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an entity failing to resubscribe does not stop the others."""
    mock_ads_device.values[SWITCH_VAR] = b"\x01"
    mock_ads_device.values["GVL.fan"] = b"\x01"
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            DOMAIN: ADS_CONFIG,
            SWITCH_DOMAIN: [
                {"platform": DOMAIN, **SWITCH_CONFIG},
                {"platform": DOMAIN, "adsvar": "GVL.fan", "name": "Fan"},
            ],
        },
    )
    await hass.async_block_till_done()
    (entry,) = hass.config_entries.async_entries(DOMAIN)

    with patch.object(
        AdsSwitch,
        "async_subscribe",
        AsyncMock(side_effect=[TypeError("closed"), None]),
    ) as mock_subscribe:
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_subscribe.call_count == 2
    assert "Error resubscribing switch." in caplog.text


async def test_reload_resubscribes_concurrently(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test a variable the PLC never answers does not hold up the other entities."""
    mock_ads_device.values[SWITCH_VAR] = b"\x01"
    mock_ads_device.values["GVL.fan"] = b"\x01"
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            DOMAIN: ADS_CONFIG,
            SWITCH_DOMAIN: [
                {"platform": DOMAIN, **SWITCH_CONFIG},
                {"platform": DOMAIN, "adsvar": "GVL.fan", "name": "Fan"},
            ],
        },
    )
    await hass.async_block_till_done()
    (entry,) = hass.config_entries.async_entries(DOMAIN)

    never_answers = asyncio.Event()
    fan_resubscribed = asyncio.Event()

    async def _async_subscribe(self: AdsEntity) -> None:
        # The pump registered first, so a serial resubscribe would wait on it.
        if self.entity_id == SWITCH_ID:
            await never_answers.wait()
        else:
            fan_resubscribed.set()

    with patch.object(AdsSwitch, "async_subscribe", _async_subscribe):
        await hass.config_entries.async_reload(entry.entry_id)
        async with asyncio.timeout(1):
            await fan_resubscribed.wait()
        never_answers.set()
        await hass.async_block_till_done()


async def test_unload_cancels_resubscribe(
    hass: HomeAssistant, mock_ads_device: MockAdsDevice
) -> None:
    """Test unloading stops a resubscription still waiting on the PLC."""
    mock_ads_device.values[SWITCH_VAR] = b"\x01"
    assert await setup_ads_platform(hass, mock_ads_device, SWITCH_DOMAIN, SWITCH_CONFIG)
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    resubscribing = asyncio.Event()

    async def _wait_forever(self: AdsEntity) -> None:
        resubscribing.set()
        await asyncio.Event().wait()

    with patch.object(AdsSwitch, "async_subscribe", _wait_forever):
        await hass.config_entries.async_setup(entry.entry_id)
        await resubscribing.wait()
        hub = get_hub(hass)
        task = hub.resubscribe_task

        await hass.config_entries.async_unload(entry.entry_id)

    assert task.cancelled()
    assert hub.resubscribe_task is None
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_subscription_on_a_closed_port(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a subscription pyads refuses because the port is closed leaves nothing to delete."""
    client = mock_pyads_connection.return_value
    # pyads returns None instead of raising when the port is not open.
    client.add_device_notification.side_effect = None
    client.add_device_notification.return_value = None
    # No first update to wait for, so setup does not need the clock moved on.
    assert await setup_ads_platform(
        hass,
        mock_ads_device,
        SWITCH_DOMAIN,
        {"adsvar": "GVL.pump", "name": "Pump"},
    )

    assert hass.states.get("switch.pump").state == STATE_UNAVAILABLE
    assert "Error subscribing to GVL.pump: the connection is not open" in caplog.text
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    client.del_device_notification.assert_not_called()


async def test_no_write_after_shutdown(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a write is not sent to the PLC once the connection is shut down."""
    caplog.set_level(logging.DEBUG)
    mock_ads_device.values["GVL.pump"] = b"\x00"
    assert await setup_ads_platform(
        hass,
        mock_ads_device,
        SWITCH_DOMAIN,
        {"adsvar": "GVL.pump", "name": "Pump"},
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # The entities are unavailable now, but the action still reaches the hub.
    await hass.services.async_call(
        DOMAIN,
        "write_data_by_name",
        {"adsvar": "GVL.pump", "adstype": "bool", "value": 1},
        blocking=True,
    )

    mock_pyads_connection.return_value.write_by_name.assert_not_called()
    assert "Not writing GVL.pump, the hub is shut down" in caplog.text


async def test_no_subscription_after_shutdown(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entities set up once the connection is shut down do not subscribe."""
    caplog.set_level(logging.DEBUG)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: ADS_CONFIG})
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # No first update to wait for, so setup does not need the clock moved on.
    assert await setup_ads_platform(
        hass,
        mock_ads_device,
        SWITCH_DOMAIN,
        {"adsvar": "GVL.pump", "name": "Pump"},
    )

    mock_pyads_connection.return_value.add_device_notification.assert_not_called()
    assert "Not subscribing to GVL.pump, the hub is shut down" in caplog.text
