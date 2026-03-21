"""Tests for Fritz!Tools coordinator."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import MagicMock, patch

from fritzconnection.lib.fritztools import ArgumentNamespace
import pytest

from homeassistant.components.fritz.const import (
    CONF_FEATURE_DEVICE_TRACKING,
    DEFAULT_CONF_FEATURE_DEVICE_TRACKING,
    DEFAULT_SSL,
    DOMAIN,
)
from homeassistant.components.fritz.coordinator import AvmWrapper, ClassSetupMissing
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MOCK_MESH_MASTER_MAC, MOCK_STATUS_DEVICE_INFO_DATA, MOCK_USER_DATA

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "attr",
    [
        "unique_id",
        "model",
        "current_firmware",
        "mac",
    ],
)
async def test_fritzboxtools_class_no_setup(
    hass: HomeAssistant,
    attr: str,
) -> None:
    """Test accessing FritzBoxTools class properties before setup."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    coordinator = AvmWrapper(
        hass=hass,
        config_entry=entry,
        host=MOCK_USER_DATA[CONF_HOST],
        port=MOCK_USER_DATA[CONF_PORT],
        username=MOCK_USER_DATA[CONF_USERNAME],
        password=MOCK_USER_DATA[CONF_PASSWORD],
        use_tls=MOCK_USER_DATA.get(CONF_SSL, DEFAULT_SSL),
        device_discovery_enabled=MOCK_USER_DATA.get(
            CONF_FEATURE_DEVICE_TRACKING, DEFAULT_CONF_FEATURE_DEVICE_TRACKING
        ),
    )

    with pytest.raises(ClassSetupMissing):
        getattr(coordinator, attr)


async def test_clear_connection_cache(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test clearing the connection cache."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED

    caplog.clear()
    fc_class_mock.return_value.clear_cache()

    assert "Cleared FritzConnection call action cache" in caplog.text


async def test_no_connection(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test no connection established."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.coordinator.FritzConnectionCached",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert (
            f"Unable to establish a connection with {MOCK_USER_DATA[CONF_HOST]}"
            in caplog.text
        )


async def test_no_software_version(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test software version non normalized."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    device_info = deepcopy(MOCK_STATUS_DEVICE_INFO_DATA)
    device_info["NewSoftwareVersion"] = "string_version_not_number"
    fs_class_mock.get_device_info = MagicMock(
        return_value=ArgumentNamespace(device_info)
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_MESH_MASTER_MAC)}
    )
    assert device
    assert device.sw_version == "string_version_not_number"
