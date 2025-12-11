"""Tests related to Powersensor's Homeassistant Integrations's background zeroconf discovery process."""

import asyncio
import importlib
from ipaddress import ip_address
import logging
from unittest.mock import Mock, call

from asyncmock import AsyncMock
import pytest
from zeroconf import ServiceInfo

from homeassistant.components.powersensor import PowersensorDiscoveryService
from homeassistant.components.powersensor.const import (
    ZEROCONF_ADD_PLUG_SIGNAL,
    ZEROCONF_REMOVE_PLUG_SIGNAL,
    ZEROCONF_UPDATE_PLUG_SIGNAL,
)
from homeassistant.components.powersensor.PowersensorDiscoveryService import (
    PowersensorServiceListener,
)
from homeassistant.core import HomeAssistant

MAC = "a4cf1218f158"


logging.getLogger().setLevel(logging.CRITICAL)


@pytest.fixture
def mock_service_info():
    """Create a mock service info."""
    return ServiceInfo(
        addresses=[ip_address("192.168.0.33").packed],
        server=f"Powersensor-gateway-{MAC}-civet.local.",
        name=f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local.",
        port=49476,
        type_="_powersensor._udp.local.",
        properties={
            "version": "1",
            "id": f"{MAC}",
        },
    )


@pytest.mark.asyncio
async def test_discovery_add(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test adding of services during Zeroconf discovery.

    This test verifies that:
    - The `add_service` method retrieves the correct service info from Zeroconf.
    - The added service trigger
    """
    mock_send = Mock()
    monkeypatch.setattr(PowersensorServiceListener, "dispatch", mock_send)
    service = PowersensorServiceListener(hass)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)
    mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    mock_send.assert_called_once_with(
        ZEROCONF_ADD_PLUG_SIGNAL, service._plugs[zc_info.name]
    )


@pytest.mark.asyncio
async def test_discovery_add_and_remove(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test adding and removing of services during Zeroconf discovery.

    This test verifies that:
    - The `add_service` method retrieves the correct service info from Zeroconf.
    - The added service triggers the correct signal when sent to Home Assistant.
    - The `remove_service` method removes the service correctly after a short debounce period.
    """
    mock_send = Mock()
    monkeypatch.setattr(PowersensorServiceListener, "dispatch", mock_send)
    # set debounce timeout very short for testing
    service = PowersensorServiceListener(hass, debounce_timeout=3)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)
    mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    mock_send.assert_called_once_with(
        ZEROCONF_ADD_PLUG_SIGNAL, service._plugs[zc_info.name]
    )

    # reset mock_send
    mock_send = Mock()
    monkeypatch.setattr(PowersensorServiceListener, "dispatch", mock_send)
    # cache plug data for checking
    data = service._plugs[zc_info.name].copy()

    service.remove_service(mock_zc, zc_info.type, zc_info.name)

    # mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)
    mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)
    mock_send.assert_not_called()
    await asyncio.sleep(service._debounce_seconds + 1)

    for _ in range(3):
        await hass.async_block_till_done()
    mock_send.assert_called_once_with(ZEROCONF_REMOVE_PLUG_SIGNAL, zc_info.name, data)


@pytest.mark.asyncio
async def test_discovery_remove_without_add(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test removing of services during Zeroconf discovery without adding first.

    This test verifies that:
    - The `remove_service` method does not call get_service_info if no add occurred.
    - The `remove_service` method triggers the correct signal when sent to Home Assistant after a short debounce period.
    """
    mock_send = Mock()
    monkeypatch.setattr(PowersensorServiceListener, "dispatch", mock_send)
    # set debounce timeout very short for testing
    service = PowersensorServiceListener(hass, debounce_timeout=3)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.remove_service(mock_zc, zc_info.type, zc_info.name)
    # mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)
    mock_zc.get_service_info.assert_not_called()
    mock_send.assert_not_called()
    await asyncio.sleep(service._debounce_seconds + 1)

    for _ in range(3):
        await hass.async_block_till_done()
    mock_send.assert_called_once_with(ZEROCONF_REMOVE_PLUG_SIGNAL, zc_info.name, None)


@pytest.mark.asyncio
async def test_discovery_remove_cancel(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test cancelling of service removal during Zeroconf discovery.

    This test verifies that:
    - The `remove_service` method does not trigger dispatch when called after an add.
    - The `get_service_info` method is called twice if add and remove are called in sequence.
    """
    mock_send = Mock()
    monkeypatch.setattr(PowersensorServiceListener, "dispatch", mock_send)
    # set debounce timeout very short for testing
    service = PowersensorServiceListener(hass, debounce_timeout=3)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)
    mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    mock_send.assert_called_once_with(
        ZEROCONF_ADD_PLUG_SIGNAL, service._plugs[zc_info.name]
    )

    # reset mock_send
    mock_send = Mock()
    monkeypatch.setattr(PowersensorServiceListener, "dispatch", mock_send)
    # cache plug data for checking

    service.remove_service(mock_zc, zc_info.type, zc_info.name)

    # mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)
    mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)
    mock_send.assert_not_called()

    service.add_service(mock_zc, zc_info.type, zc_info.name)
    assert mock_zc.get_service_info.call_count == 2
    mock_zc.get_service_info.assert_has_calls(
        [call(zc_info.type, zc_info.name), call(zc_info.type, zc_info.name)]
    )


@pytest.mark.asyncio
async def test_discovery_add_and_two_remove_calls(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test adding and removing of services during Zeroconf discovery with multiple remove calls.

    This test verifies that:
    - The `remove_service` method does not trigger dispatch when called immediately after an add.
    - The `remove_service` method triggers the correct signal after a short debounce period.
    - Multiple remove calls are properly handled by the service.
    """
    mock_send = Mock()
    monkeypatch.setattr(PowersensorServiceListener, "dispatch", mock_send)
    # set debounce timeout very short for testing
    service = PowersensorServiceListener(hass, debounce_timeout=2)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)
    mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    mock_send.assert_called_once_with(
        ZEROCONF_ADD_PLUG_SIGNAL, service._plugs[zc_info.name]
    )

    # reset mock_send
    mock_send = Mock()
    monkeypatch.setattr(PowersensorServiceListener, "dispatch", mock_send)
    # cache plug data for checking
    data = service._plugs[zc_info.name].copy()

    service.remove_service(mock_zc, zc_info.type, zc_info.name)

    # mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)
    mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)
    mock_send.assert_not_called()
    await asyncio.sleep(service._debounce_seconds // 2 + 1)
    service.remove_service(mock_zc, zc_info.type, zc_info.name)
    await asyncio.sleep(service._debounce_seconds // 2 + 1)
    for _ in range(3):
        await hass.async_block_till_done()
    mock_send.assert_called_once_with(ZEROCONF_REMOVE_PLUG_SIGNAL, zc_info.name, data)


@pytest.mark.asyncio
async def test_discovery_update(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test updating of services during Zeroconf discovery.

    This test verifies that:
    - The `update_service` method triggers the correct signal when called after an add.
    - Service properties are updated correctly with new values from Zeroconf.
    """
    mock_send = Mock()
    monkeypatch.setattr(PowersensorServiceListener, "dispatch", mock_send)
    # set debounce timeout very short for testing
    service = PowersensorServiceListener(hass, debounce_timeout=2)
    mock_zc = Mock()
    zc_info = mock_service_info
    mock_zc.get_service_info.return_value = zc_info

    service.add_service(mock_zc, zc_info.type, zc_info.name)
    mock_zc.get_service_info.assert_called_once_with(zc_info.type, zc_info.name)

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    mock_send.assert_called_once_with(
        ZEROCONF_ADD_PLUG_SIGNAL, service._plugs[zc_info.name]
    )

    # reset mock_send
    mock_send = Mock()
    monkeypatch.setattr(PowersensorServiceListener, "dispatch", mock_send)
    updated_service_info = ServiceInfo(
        addresses=[ip_address("192.168.0.34").packed],
        server=f"Powersensor-gateway-{MAC}-civet.local.",
        name=f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local.",
        port=49476,
        type_="_powersensor._udp.local.",
        properties={
            "version": "1",
            "id": f"{MAC}",
        },
    )
    mock_zc.get_service_info.return_value = updated_service_info
    service.update_service(
        mock_zc, updated_service_info.type, updated_service_info.name
    )
    for _ in range(3):
        await hass.async_block_till_done()
    mock_send.assert_called_once_with(
        ZEROCONF_UPDATE_PLUG_SIGNAL, service._plugs[zc_info.name]
    )

    assert len(service._plugs[zc_info.name]["addresses"]) == 1
    assert service._plugs[zc_info.name]["addresses"][0] == "192.168.0.34"


@pytest.mark.asyncio
async def test_discovery_dispatcher(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test dispatching of signals to the discovery service.

    This test verifies that:
    - The `async_dispatcher_send` method is correctly called with signal and arguments.
    """
    mod = importlib.import_module(
        "homeassistant.components.powersensor.PowersensorDiscoveryService"
    )
    mock_send = Mock()
    monkeypatch.setattr(mod, "async_dispatcher_send", mock_send)
    service = mod.PowersensorServiceListener(hass, debounce_timeout=4)
    service.dispatch("mock_signal", 1, 2, 3, 4)
    mock_send.assert_called_once_with(hass, "mock_signal", 1, 2, 3, 4)


@pytest.mark.asyncio
async def test_discovery_get_service_info(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_service_info
) -> None:
    """Test retrieval of service info during Zeroconf discovery.

    This test verifies that:
    - The `_async_get_service_info` method correctly retrieves and stores service info.
    - Service discoveries are properly filtered by name.
    """
    # set debounce timeout very short for testing
    service = PowersensorServiceListener(hass, debounce_timeout=5)
    mock_zc = AsyncMock()
    zc_info = mock_service_info

    def custom_call_rules(type_, name, *args, **kwargs):
        if type_ == zc_info.type and name == zc_info.name:
            return zc_info
        raise NotImplementedError

    mock_zc.async_get_service_info.side_effect = custom_call_rules

    await service._async_get_service_info(mock_zc, zc_info.type, zc_info.name)

    assert zc_info.name in service._discoveries
    assert service._discoveries[zc_info.name] == zc_info

    await service._async_get_service_info(mock_zc, zc_info.type, "garbage_name")
    assert "garbage_name" not in service._discoveries


@pytest.mark.asyncio
async def test_discovery_service_early_exit(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test early exit of the discovery service.

    This test verifies that:
    - The `start` method correctly sets up the service to exit early.
    """
    service = PowersensorDiscoveryService(hass)
    service.running = True
    await service.start()

    assert service.zc is None
    assert service.listener is None
    assert service.browser is None


@pytest.mark.asyncio
async def test_discovery_service_stop_with_canceled_task(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test stopping of the discovery service with an active task.

    This test verifies that:
    - The `stop` method correctly cancels and stops the running task.
    """
    service = PowersensorDiscoveryService(hass)
    service.running = True
    service.zc = Mock()
    service._task = asyncio.create_task(asyncio.sleep(25))
    await service.stop()
    assert service.zc is None
    assert not service.running
