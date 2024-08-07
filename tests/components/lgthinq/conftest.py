"""Configure tests for the LGThinQ integration."""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.lgthinq import THINQ_PLATFORMS
from homeassistant.components.lgthinq.const import (
    CLIENT_PREFIX,
    CONF_CONNECT_CLIENT_ID,
    CONF_ENTRY_TYPE,
    CONF_ENTRY_TYPE_THINQ,
    CONF_ENTRY_TYPE_WEBOSTV,
    CONF_SOURCES,
    DOMAIN,
    LIVE_TV_APP_ID,
    ThinqData,
)
from homeassistant.components.lgthinq.device import LGDevice
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_SECRET,
    CONF_COUNTRY,
    CONF_HOST,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from tests.common import MockConfigEntry

from .common import mock_device_info, mock_lg_device
from .const import (
    AIR_CONDITIONER,
    COOKTOP,
    DEHUMIDIFIER,
    FAKE_UUID,
    REFRIGERATOR,
    THINQ_TEST_COUNTRY,
    THINQ_TEST_PAT,
    WASHER,
    WEBOSTV_CHANNEL_1,
    WEBOSTV_CHANNEL_2,
    WEBOSTV_CLIENT_KEY,
    WEBOSTV_HOST,
    WEBOSTV_MOCK_APPS,
    WEBOSTV_MOCK_INPUTS,
    WEBOSTV_MULTI_SELECT_SOURCES,
    WEBOSTV_NAME,
)


@pytest.fixture(name="country_code")
def country_code_ficture() -> str:
    """Returns a mock conuntry code."""
    return THINQ_TEST_COUNTRY


@pytest.fixture(name="connect_client_id")
def connect_client_id_fixture() -> str:
    """Returns a mock connect client id."""
    return f"{CLIENT_PREFIX}-{str(uuid.uuid4())}"


@pytest.fixture(name="access_token")
def access_token_fixture() -> str:
    """Returns a mock connect client id."""
    return THINQ_TEST_PAT


@pytest.fixture(name="device_list")
def device_list_fixture() -> list[dict]:
    """Returns a mock device list."""
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
    """Setup the mock lghinq integration for type thinq."""
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


@pytest.fixture(name="config_entry_webostv")
async def config_entry_webostv_fixture(
    hass: HomeAssistant, unique_id=FAKE_UUID
) -> MockConfigEntry:
    """Create a mock config entry for type webostv."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: WEBOSTV_HOST,
            CONF_CLIENT_SECRET: WEBOSTV_CLIENT_KEY,
            CONF_SOURCES: WEBOSTV_MULTI_SELECT_SOURCES,
            CONF_ENTRY_TYPE: CONF_ENTRY_TYPE_WEBOSTV,
        },
        title=WEBOSTV_NAME,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)

    await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_HOST: WEBOSTV_HOST}},
    )
    await hass.async_block_till_done()
    return entry


@pytest.fixture(name="webos_client")
def webos_client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.lgthinq.WebOsClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.hello_info = {"deviceUUID": FAKE_UUID}
        client.software_info = {"major_ver": "major", "minor_ver": "minor"}
        client.system_info = {"modelName": "TVFAKE"}
        client.client_key = WEBOSTV_CLIENT_KEY
        client.apps = WEBOSTV_MOCK_APPS
        client.inputs = WEBOSTV_MOCK_INPUTS
        client.current_app_id = LIVE_TV_APP_ID

        client.channels = [WEBOSTV_CHANNEL_1, WEBOSTV_CHANNEL_2]
        client.current_channel = WEBOSTV_CHANNEL_1

        client.volume = 37
        client.sound_output = "speaker"
        client.muted = False
        client.is_on = True
        client.is_registered = Mock(return_value=True)
        client.is_connected = Mock(return_value=True)

        async def mock_state_update_callback():
            await client.register_state_update_callback.call_args[0][0](client)

        client.mock_state_update = AsyncMock(
            side_effect=mock_state_update_callback
        )

        yield client
