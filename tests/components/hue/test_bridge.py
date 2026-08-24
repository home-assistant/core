"""Test Hue bridge."""

import asyncio
from unittest.mock import Mock, patch

from aiohttp import client_exceptions
from aiohue.errors import Unauthorized
from aiohue.v1 import HueBridgeV1
from aiohue.v2 import HueBridgeV2
import pytest

from homeassistant.components.hue import bridge, migration
from homeassistant.components.hue.const import (
    CONF_ALLOW_HUE_GROUPS,
    CONF_ALLOW_UNREACHABLE,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform
from .test_light_v1 import LIGHT_RESPONSE

from tests.common import MockConfigEntry, async_capture_events


async def test_bridge_setup_v1(
    hass: HomeAssistant, mock_api_v1: Mock, device_registry: dr.DeviceRegistry
) -> None:
    """Test a successful setup for V1 bridge."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        options={CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False},
    )
    config_entry.add_to_hass(hass)

    def assert_bridge_device_registered(*args: object, **kwargs: object) -> None:
        # The bridge device must already be registered by the time platforms
        # are forwarded, so light/sensor entities can resolve it as their
        # via_device parent while they are being added.
        assert device_registry.async_get_device_by_identifier(
            (DOMAIN, mock_api_v1.config.bridge_id), config_entry.entry_id
        )

    with (
        patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            side_effect=assert_bridge_device_registered,
        ) as mock_forward,
    ):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        async with config_entry.setup_lock:
            assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v1
    assert isinstance(hue_bridge.api, HueBridgeV1)
    assert hue_bridge.api_version == 1
    assert len(mock_forward.mock_calls) == 1
    forward_entries = set(mock_forward.mock_calls[0][1][1])
    assert forward_entries == {"light", "binary_sensor", "sensor"}


async def test_bridge_device_v1(
    hass: HomeAssistant, mock_api_v1: Mock, device_registry: dr.DeviceRegistry
) -> None:
    """Test the bridge device after a full v1 setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        options={CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False},
    )
    config_entry.add_to_hass(hass)
    mock_api_v1.mock_light_responses.append(LIGHT_RESPONSE)
    mock_api_v1.mock_group_responses.append({})
    mock_api_v1.mock_sensor_responses.append({})
    events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)

    with (
        patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1),
        patch.object(migration, "is_v2_bridge", return_value=False),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    bridge_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_api_v1.config.bridge_id), config_entry.entry_id
    )
    assert bridge_device is not None
    assert bridge_device.connections == {
        (dr.CONNECTION_NETWORK_MAC, mock_api_v1.config.mac_address)
    }
    # The bridge device is registered exactly once
    create_events = [
        event
        for event in events
        if event.data["action"] == "create"
        and event.data["device_id"] == bridge_device.id
    ]
    assert len(create_events) == 1
    # The light devices resolve the bridge device as their via_device parent
    light_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "456"), config_entry.entry_id
    )
    assert light_device is not None
    assert light_device.via_device_id == bridge_device.id


async def test_bridge_device_v2(
    hass: HomeAssistant,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the bridge device after a fresh v2 setup."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    await setup_platform(hass, mock_bridge_v2, [])

    bridge_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_bridge_v2.api.config.bridge_id),
        mock_bridge_v2.config_entry.entry_id,
    )
    assert bridge_device is not None
    assert bridge_device.identifiers == {
        (DOMAIN, mock_bridge_v2.api.config.bridge_id),
        (DOMAIN, mock_bridge_v2.api.config.bridge_device.id),
    }
    # The bridge device has both the Zigbee MAC connection (set by
    # async_setup_devices) and the network MAC connection (merged in by
    # _async_register_bridge_device)
    assert bridge_device.connections == {
        (dr.CONNECTION_NETWORK_MAC, "00:17:88:01:aa:bb:fd:c7"),
        (dr.CONNECTION_NETWORK_MAC, mock_bridge_v2.api.config.mac_address),
    }
    # The bridge device is registered exactly once
    create_events = [
        event
        for event in events
        if event.data["action"] == "create"
        and event.data["device_id"] == bridge_device.id
    ]
    assert len(create_events) == 1


async def test_bridge_setup_v2(hass: HomeAssistant, mock_api_v2: Mock) -> None:
    """Test a successful setup for V2 bridge."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 2},
    )

    with (
        patch.object(bridge, "HueBridgeV2", return_value=mock_api_v2),
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
    ):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v2
    assert isinstance(hue_bridge.api, HueBridgeV2)
    assert hue_bridge.api_version == 2
    assert len(mock_forward.mock_calls) == 1
    forward_entries = set(mock_forward.mock_calls[0][1][1])
    assert forward_entries == {
        "light",
        "binary_sensor",
        "event",
        "sensor",
        "switch",
        "scene",
    }


async def test_bridge_setup_invalid_api_key(hass: HomeAssistant) -> None:
    """Test we start config flow if username is no longer whitelisted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        options={CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False},
    )
    hue_bridge = bridge.HueBridge(hass, entry)

    with (
        patch.object(hue_bridge.api, "initialize", side_effect=Unauthorized),
        patch.object(hass.config_entries.flow, "async_init") as mock_init,
    ):
        assert await hue_bridge.async_initialize_bridge() is False

    assert len(mock_init.mock_calls) == 1
    assert mock_init.mock_calls[0][2]["data"] == {"host": "1.2.3.4"}


async def test_bridge_setup_timeout(hass: HomeAssistant) -> None:
    """Test we retry to connect if we cannot connect."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        options={CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False},
    )
    hue_bridge = bridge.HueBridge(hass, entry)

    with (
        patch.object(
            hue_bridge.api,
            "initialize",
            side_effect=client_exceptions.ServerDisconnectedError,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await hue_bridge.async_initialize_bridge()


async def test_reset_unloads_entry_if_setup(
    hass: HomeAssistant, mock_api_v1: Mock
) -> None:
    """Test calling reset while the entry has been setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        options={CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False},
    )

    with (
        patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1),
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
    ):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        async with config_entry.setup_lock:
            assert await hue_bridge.async_initialize_bridge() is True

    await asyncio.sleep(0)

    assert len(hass.services.async_services()) == 0
    assert len(mock_forward.mock_calls) == 1

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_forward:
        assert await hue_bridge.async_reset()

    assert len(mock_forward.mock_calls) == 3
    assert len(hass.services.async_services()) == 0


async def test_handle_unauthorized(hass: HomeAssistant, mock_api_v1: Mock) -> None:
    """Test handling an unauthorized error on update."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        options={CONF_ALLOW_HUE_GROUPS: False, CONF_ALLOW_UNREACHABLE: False},
    )

    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        async with config_entry.setup_lock:
            assert await hue_bridge.async_initialize_bridge() is True

    with patch.object(bridge, "create_config_flow") as mock_create:
        await hue_bridge.handle_unauthorized_error()

    assert hue_bridge.authorized is False
    assert len(mock_create.mock_calls) == 1
    assert mock_create.mock_calls[0][1][1] == "1.2.3.4"
