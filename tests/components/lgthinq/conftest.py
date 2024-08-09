"""Configure tests for the LGThinQ integration."""

from unittest.mock import patch
import uuid

import pytest

from homeassistant.components.lgthinq import THINQ_PLATFORMS
from homeassistant.components.lgthinq.const import (
    CLIENT_PREFIX,
    CONF_CONNECT_CLIENT_ID,
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_THINQ,
    DOMAIN,
    ThinqData,
)
from homeassistant.components.lgthinq.device import LGDevice
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY
from homeassistant.core import HomeAssistant

from .common import mock_device_info, mock_lg_device
from .const import (
    AIR_CONDITIONER,
    COOKTOP,
    DEHUMIDIFIER,
    REFRIGERATOR,
    THINQ_TEST_COUNTRY,
    THINQ_TEST_PAT,
    WASHER,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="country_code")
def country_code_ficture() -> str:
    """Return a mock conuntry code."""
    return THINQ_TEST_COUNTRY


@pytest.fixture(name="connect_client_id")
def connect_client_id_fixture() -> str:
    """Return a mock connect client id."""
    return f"{CLIENT_PREFIX}-{uuid.uuid4()!s}"


@pytest.fixture(name="access_token")
def access_token_fixture() -> str:
    """Return a mock connect client id."""
    return THINQ_TEST_PAT


@pytest.fixture(name="device_list")
def device_list_fixture() -> list[dict]:
    """Return a mock device list."""
    return [
        mock_device_info(AIR_CONDITIONER),
        mock_device_info(COOKTOP),
        mock_device_info(DEHUMIDIFIER),
        mock_device_info(REFRIGERATOR),
        mock_device_info(WASHER),
    ]


@pytest.fixture(name="config_entry_thinq")
def config_entry_thinq_fixture(
    country_code: str, connect_client_id: str, access_token: str
) -> MockConfigEntry:
    """Create a mock config entry for type thinq."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Test {DOMAIN} for type thinq",
        unique_id=access_token,
        data={
            CONF_ENTRY_TYPE: CONF_ENTRY_TYPE_THINQ,
            CONF_COUNTRY: country_code,
            CONF_CONNECT_CLIENT_ID: connect_client_id,
            CONF_ACCESS_TOKEN: access_token,
        },
    )


@pytest.fixture(name="init_integration_thinq")
async def init_integration_thinq_fixture(
    hass: HomeAssistant,
    config_entry_thinq: MockConfigEntry,
    device_list: list[dict],
) -> MockConfigEntry:
    """Set up a mock lghinq integration for type thinq."""
    config_entry_thinq.add_to_hass(hass)

    with patch(
        "homeassistant.components.lgthinq.async_setup_entry_thinq",
        return_value=True,
    ):
        await hass.config_entries.async_setup(config_entry_thinq.entry_id)

    lg_devices: list[LGDevice] = []
    for device_info in device_list:
        lg_devices.extend(await mock_lg_device(hass, device_info))

    assert isinstance(config_entry_thinq.runtime_data, ThinqData)
    config_entry_thinq.runtime_data.lge_devices = lg_devices
    await hass.config_entries.async_forward_entry_setups(
        config_entry_thinq, THINQ_PLATFORMS
    )

    await hass.async_block_till_done()

    return config_entry_thinq
