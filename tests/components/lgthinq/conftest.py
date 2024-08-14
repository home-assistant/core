"""Configure tests for the LGThinQ integration."""

from typing import Any
from unittest.mock import patch
import uuid

import pytest

from homeassistant.components.lgthinq import PLATFORMS, ThinqData
from homeassistant.components.lgthinq.const import (
    CLIENT_PREFIX,
    CONF_CONNECT_CLIENT_ID,
    DOMAIN,
)
from homeassistant.components.lgthinq.device import LGDevice
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY
from homeassistant.core import HomeAssistant

from .common import mock_device_info, mock_lg_device
from .const import (
    AIR_CONDITIONER,
    COOKTOP,
    DEHUMIDIFIER,
    MOCK_COUNTRY,
    MOCK_PAT,
    REFRIGERATOR,
    WASHER,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="country_code")
def country_code_ficture() -> str:
    """Return a mock country code."""
    return MOCK_COUNTRY


@pytest.fixture(name="connect_client_id")
def connect_client_id_fixture() -> str:
    """Return a mock connect client id."""
    return f"{CLIENT_PREFIX}-{uuid.uuid4()!s}"


@pytest.fixture(name="access_token")
def access_token_fixture() -> str:
    """Return a mock connect client id."""
    return MOCK_PAT


@pytest.fixture(name="device_list")
def device_list_fixture() -> list[dict[str, Any]]:
    """Return a mock device list."""
    return [
        mock_device_info(AIR_CONDITIONER),
        mock_device_info(COOKTOP),
        mock_device_info(DEHUMIDIFIER),
        mock_device_info(REFRIGERATOR),
        mock_device_info(WASHER),
    ]


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    country_code: str, connect_client_id: str, access_token: str
) -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Test {DOMAIN} entry",
        unique_id=access_token,
        data={
            CONF_COUNTRY: country_code,
            CONF_CONNECT_CLIENT_ID: connect_client_id,
            CONF_ACCESS_TOKEN: access_token,
        },
    )


@pytest.fixture(name="init_integration")
async def init_integration_fixture(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_list: list[dict[str, Any]],
) -> MockConfigEntry:
    """Set up a mock lghinq integration for type thinq."""
    assert config_entry
    config_entry.add_to_hass(hass)
    config_entry.runtime_data = ThinqData()

    with patch(
        "homeassistant.components.lgthinq.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    lg_device_list: list[LGDevice] = []
    for device_info in device_list:
        lg_devices = await mock_lg_device(hass, device_info)
        assert lg_devices
        lg_device_list.extend(lg_devices)

    lg_device_map = {lg_device.id: lg_device for lg_device in lg_device_list}

    config_entry.runtime_data.device_map = lg_device_map
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    await hass.async_block_till_done()

    return config_entry
