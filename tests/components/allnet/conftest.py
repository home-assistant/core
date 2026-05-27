"""Fixtures for ALLNET integration tests."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from allnet.models import Channel, ChannelKind, ChannelState, DeviceInfo, DeviceProfile
import pytest
import pytest_asyncio

from homeassistant import config_entries, loader
from homeassistant.components.allnet.const import (
    CONF_DEVICE_PROFILE,
    CONF_USE_SSL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    category_registry as cr,
    device_registry as dr,
    entity,
    entity_registry as er,
    floor_registry as fr,
    frame,
    issue_registry as ir,
    label_registry as lr,
    restore_state,
    template,
    translation,
)
from homeassistant.helpers.storage import get_internal_store_manager
from homeassistant.util.async_ import create_eager_task

# ---------------------------------------------------------------------------
# Default test data
# ---------------------------------------------------------------------------

TEST_HOST = "192.0.2.10"
TEST_UNIQUE_ID = "000fc90ecb31"
TEST_MAC = "00:0f:c9:0e:cb:31"


# ---------------------------------------------------------------------------
# HomeAssistant bootstrap fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def hass(tmp_path) -> AsyncGenerator[HomeAssistant]:
    """Create a minimal HomeAssistant instance for testing."""
    config_dir = str(tmp_path)

    _hass = HomeAssistant(config_dir)
    # recovery_mode enables load_empty for all registries (no disk I/O)
    _hass.config.recovery_mode = True

    loader.async_setup(_hass)
    entity.async_setup(_hass)
    frame.async_setup(_hass)
    template.async_setup(_hass)
    translation.async_setup(_hass)
    dr.async_setup(_hass)

    _hass.config_entries = config_entries.ConfigEntries(_hass, {})

    await asyncio.gather(
        create_eager_task(get_internal_store_manager(_hass).async_initialize()),
        create_eager_task(ar.async_load(_hass, load_empty=True)),
        create_eager_task(cr.async_load(_hass, load_empty=True)),
        create_eager_task(dr.async_load(_hass, load_empty=True)),
        create_eager_task(er.async_load(_hass, load_empty=True)),
        create_eager_task(fr.async_load(_hass, load_empty=True)),
        create_eager_task(ir.async_load(_hass, load_empty=True)),
        create_eager_task(lr.async_load(_hass, load_empty=True)),
        create_eager_task(restore_state.async_load(_hass, load_empty=True)),
        create_eager_task(_hass.config_entries.async_initialize()),
    )

    _hass.set_state(CoreState.running)

    yield _hass

    await _hass.async_stop(force=True)


# ---------------------------------------------------------------------------
# allnet library mock data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_device_info() -> DeviceInfo:
    """Return a mock DeviceInfo."""
    return DeviceInfo(
        profile=DeviceProfile.MSR,
        unique_id=TEST_UNIQUE_ID,
        name="ALLNET Test Device",
        model="ALL3500",
        sw_version="1.2.3",
        hw_version="1.0",
        mac_address=TEST_MAC,
        raw={"version": "1.2.3", "model": "ALL3500"},
    )


@pytest.fixture
def mock_channels() -> tuple[Channel, ...]:
    """Return a tuple of mock channels (sensor + binary_sensor + switch)."""
    return (
        Channel(
            id="temp_0",
            kind=ChannelKind.SENSOR,
            name="Temperature",
            value=22.5,
            unit="°C",
            raw={"info": {"chipid": "12", "unit": "°C"}},
        ),
        Channel(
            id="current_0",
            kind=ChannelKind.SENSOR,
            name="Current",
            value=1.5,
            unit="A",
            raw={"info": {"chipid": "20", "unit": "A"}},
        ),
        Channel(
            id="humidity_0",
            kind=ChannelKind.SENSOR,
            name="Humidity",
            value=None,  # unavailable
            unit="%",
            raw={"info": {"chipid": "13", "unit": "%"}},
        ),
        Channel(
            id="door_0",
            kind=ChannelKind.BINARY_SENSOR,
            name="Door Contact",
            value=False,
            raw={
                "info": {"chipid": "74", "unit": ""},
                "digitalToText": "offen/geschlossen",
            },
        ),
        Channel(
            id="motion_0",
            kind=ChannelKind.BINARY_SENSOR,
            name="Motion Sensor",
            value=True,
            raw={
                "info": {"chipid": "74", "unit": ""},
                "digitalToText": "motion erkannt",
            },
        ),
        Channel(
            id="relay_0",
            kind=ChannelKind.SWITCH,
            name="Relay 1",
            value=False,
            raw={"info": {"chipid": "99", "unit": ""}},
        ),
        Channel(
            id="relay_1",
            kind=ChannelKind.SWITCH,
            name="Relay 2",
            value=True,
            raw={"info": {"chipid": "99", "unit": ""}},
        ),
    )


@pytest.fixture
def mock_allnet_client(mock_device_info, mock_channels):
    """Return a mock AllnetClient."""
    client = MagicMock()
    client.async_get_device_info = AsyncMock(return_value=mock_device_info)
    client.async_get_channels = AsyncMock(return_value=mock_channels)
    client.async_set_channel_state = AsyncMock(
        return_value=ChannelState(channel_id="relay_0", value=True)
    )
    return client


# ---------------------------------------------------------------------------
# Config entry fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def config_entry_data() -> dict[str, Any]:
    """Return default config entry data."""
    return {
        CONF_HOST: TEST_HOST,
        CONF_USE_SSL: False,
        CONF_DEVICE_PROFILE: "auto",
    }


@pytest.fixture
def config_entry(config_entry_data) -> ConfigEntry:
    """Return a config entry (not yet added to hass)."""
    return ConfigEntry(
        data=config_entry_data,
        discovery_keys={},
        domain=DOMAIN,
        minor_version=1,
        options={},
        source=config_entries.SOURCE_USER,
        subentries_data=None,
        title="ALLNET Test Device",
        unique_id=TEST_UNIQUE_ID,
        version=1,
    )


@pytest_asyncio.fixture
async def setup_integration(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    mock_allnet_client: MagicMock,
) -> AsyncGenerator[ConfigEntry]:
    """Set up the ALLNET integration with a mock client and yield the entry."""
    mock_session = MagicMock()
    with (
        patch(
            "homeassistant.components.allnet.AllnetClient",
            return_value=mock_allnet_client,
        ),
        patch(
            "homeassistant.components.allnet.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        await hass.config_entries.async_add(config_entry)
        await hass.async_block_till_done()

    yield config_entry
