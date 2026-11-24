"""Test the ADS entity lifecycle."""

import asyncio
from collections.abc import Callable
import threading
from typing import Any
from unittest.mock import MagicMock, call

import pyads
import pytest

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockAdsDevice, build_notification, setup_ads_platform

ADS_VAR = "GVL.pump"
ENTITY_ID = "switch.pump"
PLATFORM_CONFIG = {"adsvar": ADS_VAR, "name": "Pump"}

BOOL_TRUE = b"\x01"
BOOL_FALSE = b"\x00"


async def test_removal_deletes_the_notification(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test removing an entity deletes its notification on the PLC."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE
    assert await setup_ads_platform(
        hass, mock_ads_device, SWITCH_DOMAIN, PLATFORM_CONFIG
    )

    entity_registry.async_remove(ENTITY_ID)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is None
    client = mock_pyads_connection.return_value
    client.del_device_notification.assert_called_once_with(1, 1)

    # Stopping afterwards does not delete it a second time.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    client.del_device_notification.assert_called_once()


async def test_select_removal_deletes_both_notifications(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test removing a select deletes the option subscription as well."""
    mock_ads_device.values["GVL.mode"] = b"\x01\x00"
    assert await setup_ads_platform(
        hass,
        mock_ads_device,
        SELECT_DOMAIN,
        {"adsvar": "GVL.mode", "name": "Mode", "options": ["off", "auto"]},
    )
    assert hass.states.get("select.mode").state == "auto"

    entity_registry.async_remove("select.mode")
    await hass.async_block_till_done()

    client = mock_pyads_connection.return_value
    assert client.del_device_notification.call_args_list == [call(1, 1), call(2, 2)]


async def test_removal_after_shutdown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test removing an entity after shutdown does not delete its notification again."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE
    assert await setup_ads_platform(
        hass, mock_ads_device, SWITCH_DOMAIN, PLATFORM_CONFIG
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    client = mock_pyads_connection.return_value
    client.del_device_notification.assert_called_once_with(1, 1)

    entity_registry.async_remove(ENTITY_ID)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is None
    client.del_device_notification.assert_called_once()


async def test_entity_id_change_keeps_the_subscription(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test an entity renamed in the registry still follows the PLC."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE
    assert await setup_ads_platform(
        hass, mock_ads_device, SWITCH_DOMAIN, PLATFORM_CONFIG
    )

    entity_registry.async_update_entity(ENTITY_ID, new_entity_id="switch.main_pump")
    await hass.async_block_till_done()

    # Renamed in place, so the subscription is neither dropped nor made again.
    client = mock_pyads_connection.return_value
    client.del_device_notification.assert_not_called()
    client.add_device_notification.assert_called_once()
    await mock_ads_device.async_push(hass, ADS_VAR, BOOL_FALSE)
    assert hass.states.get("switch.main_pump").state == STATE_OFF


async def test_removal_delete_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a notification the PLC fails to delete is logged, and the entity still goes."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE
    assert await setup_ads_platform(
        hass, mock_ads_device, SWITCH_DOMAIN, PLATFORM_CONFIG
    )
    client = mock_pyads_connection.return_value
    client.del_device_notification.side_effect = pyads.ADSError(err_code=1861)

    entity_registry.async_remove(ENTITY_ID)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is None
    assert "timeout elapsed (1861)" in caplog.text


async def test_removal_while_subscribing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test an entity removed while its subscription is in flight deletes it on arrival."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE
    client = mock_pyads_connection.return_value
    subscribing = threading.Event()
    release = threading.Event()

    def add_device_notification(*args: Any) -> tuple[int, int]:
        subscribing.set()
        release.wait()
        return mock_ads_device.add_device_notification(*args)

    client.add_device_notification.side_effect = add_device_notification
    setup = hass.async_create_task(
        setup_ads_platform(hass, mock_ads_device, SWITCH_DOMAIN, PLATFORM_CONFIG)
    )
    await hass.async_add_executor_job(subscribing.wait)

    entity_registry.async_remove(ENTITY_ID)
    await asyncio.sleep(0)
    release.set()
    assert await setup

    # Only the PLC side is checked: core still writes the state of an entity
    # removed while its async_added_to_hass was awaiting.
    client.del_device_notification.assert_called_once_with(1, 1)


def _remove_entity(hass: HomeAssistant) -> None:
    """Remove the entity from the registry."""
    er.async_get(hass).async_remove(ENTITY_ID)


def _stop_hass(hass: HomeAssistant) -> None:
    """Stop Home Assistant, which shuts the hub down."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)


@pytest.mark.parametrize(
    "delete",
    [
        pytest.param(_remove_entity, id="removal"),
        pytest.param(_stop_hass, id="shutdown"),
    ],
)
async def test_notification_while_deleting(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
    delete: Callable[[HomeAssistant], None],
) -> None:
    """Test a notification still in flight while it is deleted is not unknown."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE
    assert await setup_ads_platform(
        hass, mock_ads_device, SWITCH_DOMAIN, PLATFORM_CONFIG
    )
    client = mock_pyads_connection.return_value
    _, _, router_callback = client.add_device_notification.call_args.args

    def del_device_notification(hnotify: int, _huser: int) -> None:
        # The router finishes delivering before the delete returns.
        router_callback(build_notification(hnotify, BOOL_FALSE), ADS_VAR)

    client.del_device_notification.side_effect = del_device_notification
    delete(hass)
    await hass.async_block_till_done()

    client.del_device_notification.assert_called_once_with(1, 1)
    assert "Unknown device notification handle" not in caplog.text


async def test_shutdown_waits_for_a_removal(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test shutdown does not close the connection while a removal is deleting."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE
    assert await setup_ads_platform(
        hass, mock_ads_device, SWITCH_DOMAIN, PLATFORM_CONFIG
    )
    client = mock_pyads_connection.return_value
    deleting = threading.Event()
    release = threading.Event()

    def del_device_notification(*_: Any) -> None:
        deleting.set()
        release.wait()

    client.del_device_notification.side_effect = del_device_notification
    entity_registry.async_remove(ENTITY_ID)
    await hass.async_add_executor_job(deleting.wait)

    # The stop listener runs the shutdown in the executor, next to the delete.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    try:
        await asyncio.sleep(0.05)
        client.close.assert_not_called()
    finally:
        # Never leave the delete blocked, or a failure hangs the test run.
        release.set()
    await hass.async_block_till_done()

    # The removal deleted the notification, so shutdown had nothing left to delete.
    client.del_device_notification.assert_called_once_with(1, 1)
    client.close.assert_called_once()
