"""Tests for the GogoGate2 component."""

from unittest.mock import MagicMock, patch

from ismartgate import GogoGate2Api
import pytest

from homeassistant.components.gogogate2 import DEVICE_TYPE_GOGOGATE2, async_setup_entry
from homeassistant.components.gogogate2.const import DEVICE_TYPE_ISMARTGATE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


@patch("homeassistant.components.gogogate2.common.GogoGate2Api")
async def test_config_update(gogogate2api_mock, hass: HomeAssistant) -> None:
    """Test config setup where the config is updated."""

    api = MagicMock(GogoGate2Api)
    api.async_info.side_effect = Exception("Error")
    gogogate2api_mock.return_value = api

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry_id=config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.data == {
        CONF_DEVICE: DEVICE_TYPE_GOGOGATE2,
        CONF_IP_ADDRESS: "127.0.0.1",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
    }


@patch("homeassistant.components.gogogate2.common.ISmartGateApi")
async def test_config_no_update(ismartgateapi_mock, hass: HomeAssistant) -> None:
    """Test config setup where the data is not updated."""
    api = MagicMock(GogoGate2Api)
    api.async_info.side_effect = Exception("Error")
    ismartgateapi_mock.return_value = api

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_DEVICE: DEVICE_TYPE_ISMARTGATE,
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry_id=config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.data == {
        CONF_DEVICE: DEVICE_TYPE_ISMARTGATE,
        CONF_IP_ADDRESS: "127.0.0.1",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
    }


async def test_api_failure_on_startup(hass: HomeAssistant) -> None:
    """Test api failure on startup raises ConfigEntryNotReady."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_DEVICE: DEVICE_TYPE_ISMARTGATE,
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.gogogate2.common.ISmartGateApi.async_info",
            side_effect=TimeoutError,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, config_entry)
