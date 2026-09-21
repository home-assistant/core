"""Test the ADS entity lifecycle."""

import asyncio
import logging
import threading
from typing import Any
from unittest.mock import MagicMock

import pyads
import pytest

from homeassistant.components.ads.const import DATA_ADS
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_OFF, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockAdsDevice, setup_ads_platform

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
    assert await setup_ads_platform(hass, SWITCH_DOMAIN, PLATFORM_CONFIG)

    entity_registry.async_remove(ENTITY_ID)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is None
    client = mock_pyads_connection.return_value
    client.del_device_notification.assert_called_once_with(1, 1)

    # Stopping afterwards does not delete it a second time.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    client.del_device_notification.assert_called_once()


async def test_entity_id_change_keeps_the_subscription(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test an entity renamed in the registry still follows the PLC."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE
    assert await setup_ads_platform(hass, SWITCH_DOMAIN, PLATFORM_CONFIG)

    entity_registry.async_update_entity(ENTITY_ID, new_entity_id="switch.main_pump")
    await hass.async_block_till_done()

    # Renamed in place, so the subscription is neither dropped nor made again.
    client = mock_pyads_connection.return_value
    client.del_device_notification.assert_not_called()
    client.add_device_notification.assert_called_once()
    await mock_ads_device.async_push(hass, ADS_VAR, BOOL_FALSE)
    assert hass.states.get("switch.main_pump").state == STATE_OFF


async def test_subscription_on_a_closed_port(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test a subscription pyads refuses because the port is closed leaves nothing to delete."""
    client = mock_pyads_connection.return_value
    # pyads returns None instead of raising when the port is not open.
    client.add_device_notification.return_value = None
    assert await setup_ads_platform(hass, SWITCH_DOMAIN, PLATFORM_CONFIG)

    entity_registry.async_remove(ENTITY_ID)
    await hass.async_block_till_done()

    client.del_device_notification.assert_not_called()


async def test_no_io_after_shutdown(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test nothing is sent to the PLC once the connection is shut down."""
    caplog.set_level(logging.DEBUG)
    mock_ads_device.values[ADS_VAR] = BOOL_FALSE
    assert await setup_ads_platform(hass, SWITCH_DOMAIN, PLATFORM_CONFIG)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_ON,
        {TargetKey.ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_pyads_connection.return_value.write_by_name.assert_not_called()
    assert f"Not writing {ADS_VAR}, the hub is shut down" in caplog.text


async def test_removal_delete_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a notification the PLC fails to delete is logged, and the entity still goes."""
    mock_ads_device.values[ADS_VAR] = BOOL_TRUE
    assert await setup_ads_platform(hass, SWITCH_DOMAIN, PLATFORM_CONFIG)
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
        setup_ads_platform(hass, SWITCH_DOMAIN, PLATFORM_CONFIG)
    )
    await hass.async_add_executor_job(subscribing.wait)

    entity_registry.async_remove(ENTITY_ID)
    await asyncio.sleep(0)
    release.set()
    assert await setup

    client.del_device_notification.assert_called_once_with(1, 1)


@pytest.mark.parametrize(
    ("method", "args", "message"),
    [
        pytest.param(
            "read_by_name",
            (ADS_VAR, pyads.PLCTYPE_BOOL),
            f"Not reading {ADS_VAR}, the hub is shut down",
            id="read",
        ),
        pytest.param(
            "add_device_notification",
            (ADS_VAR, pyads.PLCTYPE_BOOL, lambda *_: None),
            f"Not subscribing to {ADS_VAR}, the hub is shut down",
            id="subscribe",
        ),
    ],
)
@pytest.mark.usefixtures("setup_ads")
async def test_hub_refuses_io_after_shutdown(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    caplog: pytest.LogCaptureFixture,
    method: str,
    args: tuple[Any, ...],
    message: str,
) -> None:
    """Test the hub sends nothing once it is shut down."""
    caplog.set_level(logging.DEBUG)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    hub = hass.data[DATA_ADS]
    assert await hass.async_add_executor_job(getattr(hub, method), *args) is None

    getattr(mock_pyads_connection.return_value, method).assert_not_called()
    assert message in caplog.text
