"""Tests for ZHA integration init."""
import asyncio
import typing
from unittest.mock import AsyncMock, Mock, patch

import pytest
from zigpy.application import ControllerApplication
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH
from zigpy.exceptions import TransientConnectionError

from homeassistant.components.zha.core.const import (
    CONF_BAUDRATE,
    CONF_FLOW_CONTROL,
    CONF_RADIO_TYPE,
    CONF_USB_PATH,
    DOMAIN,
)
from homeassistant.components.zha.core.helpers import get_zha_data
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    MAJOR_VERSION,
    MINOR_VERSION,
    Platform,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.setup import async_setup_component

from .test_light import LIGHT_ON_OFF

from tests.common import MockConfigEntry

DATA_RADIO_TYPE = "ezsp"
DATA_PORT_PATH = "/dev/serial/by-id/FTDI_USB__-__Serial_Cable_12345678-if00-port0"


@pytest.fixture(autouse=True)
def disable_platform_only():
    """Disable platforms to speed up tests."""
    with patch("homeassistant.components.zha.PLATFORMS", []):
        yield


@pytest.fixture
def config_entry_v1(hass):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_RADIO_TYPE: DATA_RADIO_TYPE, CONF_USB_PATH: DATA_PORT_PATH},
        version=1,
    )


@pytest.mark.parametrize("config", ({}, {DOMAIN: {}}))
@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_migration_from_v1_no_baudrate(
    hass: HomeAssistant, config_entry_v1, config
) -> None:
    """Test migration of config entry from v1."""
    config_entry_v1.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)

    assert config_entry_v1.data[CONF_RADIO_TYPE] == DATA_RADIO_TYPE
    assert CONF_DEVICE in config_entry_v1.data
    assert config_entry_v1.data[CONF_DEVICE][CONF_DEVICE_PATH] == DATA_PORT_PATH
    assert CONF_USB_PATH not in config_entry_v1.data
    assert config_entry_v1.version == 4


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_migration_from_v1_with_baudrate(
    hass: HomeAssistant, config_entry_v1
) -> None:
    """Test migration of config entry from v1 with baudrate in config."""
    config_entry_v1.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_BAUDRATE: 115200}})

    assert config_entry_v1.data[CONF_RADIO_TYPE] == DATA_RADIO_TYPE
    assert CONF_DEVICE in config_entry_v1.data
    assert config_entry_v1.data[CONF_DEVICE][CONF_DEVICE_PATH] == DATA_PORT_PATH
    assert CONF_USB_PATH not in config_entry_v1.data
    assert CONF_BAUDRATE in config_entry_v1.data[CONF_DEVICE]
    assert config_entry_v1.data[CONF_DEVICE][CONF_BAUDRATE] == 115200
    assert config_entry_v1.version == 4


@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_migration_from_v1_wrong_baudrate(
    hass: HomeAssistant, config_entry_v1
) -> None:
    """Test migration of config entry from v1 with wrong baudrate."""
    config_entry_v1.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_BAUDRATE: 115222}})

    assert config_entry_v1.data[CONF_RADIO_TYPE] == DATA_RADIO_TYPE
    assert CONF_DEVICE in config_entry_v1.data
    assert config_entry_v1.data[CONF_DEVICE][CONF_DEVICE_PATH] == DATA_PORT_PATH
    assert CONF_USB_PATH not in config_entry_v1.data
    assert config_entry_v1.version == 4


@pytest.mark.skipif(
    MAJOR_VERSION != 0 or (MAJOR_VERSION == 0 and MINOR_VERSION >= 112),
    reason="Not applicaable for this version",
)
@pytest.mark.parametrize(
    "zha_config",
    (
        {},
        {CONF_USB_PATH: "str"},
        {CONF_RADIO_TYPE: "ezsp"},
        {CONF_RADIO_TYPE: "ezsp", CONF_USB_PATH: "str"},
    ),
)
async def test_config_depreciation(hass: HomeAssistant, zha_config) -> None:
    """Test config option depreciation."""

    with patch(
        "homeassistant.components.zha.async_setup", return_value=True
    ) as setup_mock:
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: zha_config})
        assert setup_mock.call_count == 1


@pytest.mark.parametrize(
    ("path", "cleaned_path"),
    [
        # No corrections
        ("/dev/path1", "/dev/path1"),
        ("/dev/path1[asd]", "/dev/path1[asd]"),
        ("/dev/path1 ", "/dev/path1 "),
        ("socket://1.2.3.4:5678", "socket://1.2.3.4:5678"),
        # Brackets around URI
        ("socket://[1.2.3.4]:5678", "socket://1.2.3.4:5678"),
        # Spaces
        ("socket://dev/path1 ", "socket://dev/path1"),
        # Both
        ("socket://[1.2.3.4]:5678 ", "socket://1.2.3.4:5678"),
    ],
)
@patch("homeassistant.components.zha.setup_quirks", Mock(return_value=True))
@patch(
    "homeassistant.components.zha.websocket_api.async_load_api", Mock(return_value=True)
)
async def test_setup_with_v3_cleaning_uri(
    hass: HomeAssistant,
    path: str,
    cleaned_path: str,
    mock_zigpy_connect: ControllerApplication,
) -> None:
    """Test migration of config entry from v3, applying corrections to the port path."""
    config_entry_v4 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_RADIO_TYPE: DATA_RADIO_TYPE,
            CONF_DEVICE: {
                CONF_DEVICE_PATH: path,
                CONF_BAUDRATE: 115200,
                CONF_FLOW_CONTROL: None,
            },
        },
        version=4,
    )
    config_entry_v4.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry_v4.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry_v4.entry_id)

    assert config_entry_v4.data[CONF_RADIO_TYPE] == DATA_RADIO_TYPE
    assert config_entry_v4.data[CONF_DEVICE][CONF_DEVICE_PATH] == cleaned_path
    assert config_entry_v4.version == 4


@pytest.mark.parametrize(
    (
        "radio_type",
        "old_baudrate",
        "old_flow_control",
        "new_baudrate",
        "new_flow_control",
    ),
    [
        ("znp", None, None, 115200, None),
        ("znp", None, "software", 115200, "software"),
        ("znp", 57600, "software", 57600, "software"),
        ("deconz", None, None, 38400, None),
        ("deconz", 115200, None, 115200, None),
    ],
)
@patch("homeassistant.components.zha.async_setup_entry", AsyncMock(return_value=True))
async def test_migration_baudrate_and_flow_control(
    radio_type: str,
    old_baudrate: int,
    old_flow_control: typing.Literal["hardware", "software", None],
    new_baudrate: int,
    new_flow_control: typing.Literal["hardware", "software", None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test baudrate and flow control migration."""
    config_entry.data = {
        **config_entry.data,
        CONF_RADIO_TYPE: radio_type,
        CONF_DEVICE: {
            CONF_BAUDRATE: old_baudrate,
            CONF_FLOW_CONTROL: old_flow_control,
            CONF_DEVICE_PATH: "/dev/null",
        },
    }
    config_entry.version = 3
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version > 3
    assert config_entry.data[CONF_DEVICE][CONF_BAUDRATE] == new_baudrate
    assert config_entry.data[CONF_DEVICE][CONF_FLOW_CONTROL] == new_flow_control


@patch(
    "homeassistant.components.zha.PLATFORMS",
    [Platform.LIGHT, Platform.BUTTON, Platform.SENSOR, Platform.SELECT],
)
async def test_zha_retry_unique_ids(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    zigpy_device_mock,
    mock_zigpy_connect: ControllerApplication,
    caplog,
) -> None:
    """Test that ZHA retrying creates unique entity IDs."""

    config_entry.add_to_hass(hass)

    # Ensure we have some device to try to load
    app = mock_zigpy_connect
    light = zigpy_device_mock(LIGHT_ON_OFF)
    app.devices[light.ieee] = light

    # Re-try setup but have it fail once, so entities have two chances to be created
    with patch.object(
        app,
        "startup",
        side_effect=[TransientConnectionError(), None],
    ) as mock_connect:
        with patch(
            "homeassistant.config_entries.async_call_later",
            lambda hass, delay, action: async_call_later(hass, 0, action),
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

            # Wait for the config entry setup to retry
            await asyncio.sleep(0.1)

        assert len(mock_connect.mock_calls) == 2

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert "does not generate unique IDs" not in caplog.text


async def test_shutdown_on_ha_stop(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_zigpy_connect: ControllerApplication,
) -> None:
    """Test that the ZHA gateway is stopped when HA is shut down."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    zha_data = get_zha_data(hass)

    with patch.object(
        zha_data.gateway, "shutdown", wraps=zha_data.gateway.shutdown
    ) as mock_shutdown:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        hass.set_state(CoreState.stopping)
        await hass.async_block_till_done()

    assert len(mock_shutdown.mock_calls) == 1
