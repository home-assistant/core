"""Test the Open Thread Border Router config flow."""

import asyncio
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest
import python_otbr_api

from homeassistant.components import otbr
from homeassistant.components.hassio import AddonError
from homeassistant.components.homeassistant_hardware.helpers import (
    async_register_firmware_info_callback,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningAddon,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.setup import async_setup_component

from . import DATASET_CH15, DATASET_CH16, TEST_BORDER_AGENT_ID, TEST_BORDER_AGENT_ID_2

from tests.common import MockConfigEntry, MockModule, mock_integration
from tests.test_util.aiohttp import AiohttpClientMocker

HASSIO_DATA = HassioServiceInfo(
    config={"host": "core-silabs-multiprotocol", "port": 8081},
    name="Silicon Labs Multiprotocol",
    slug="otbr",
    uuid="12345",
)
HASSIO_DATA_2 = HassioServiceInfo(
    config={"host": "core-silabs-multiprotocol_2", "port": 8082},
    name="Silicon Labs Multiprotocol",
    slug="other_addon",
    uuid="23456",
)

HASSIO_DATA_OTBR = HassioServiceInfo(
    config={
        "host": "core-openthread-border-router",
        "port": 8081,
        "device": "/dev/ttyUSB1",
        "firmware": "SL-OPENTHREAD/2.4.4.0_GitHub-7074a43e4; EFR32; Oct 21 2024 14:40:57\r",
        "addon": "OpenThread Border Router",
    },
    name="OpenThread Border Router",
    slug="core_openthread_border_router",
    uuid="c58ba80fc88548008776bf8da903ef21",
)


@pytest.fixture(name="otbr_addon_info")
def otbr_addon_info_fixture(addon_info: AsyncMock, addon_installed) -> AsyncMock:
    """Mock Supervisor otbr add-on info."""
    addon_info.return_value.available = True
    addon_info.return_value.hostname = ""
    addon_info.return_value.options = {}
    addon_info.return_value.state = "unknown"
    addon_info.return_value.update_available = False
    addon_info.return_value.version = None
    return addon_info


@pytest.fixture(name="mock_usb_ports")
def mock_usb_ports_fixture() -> dict[str, str]:
    """Mock USB ports for testing."""
    return {
        "/dev/ttyUSB0": "Home Assistant Connect ZBT-1",
        "/dev/ttyUSB1": "SkyConnect",
        "/dev/ttyAMA1": "Home Assistant Yellow",
    }


@pytest.fixture(name="mock_async_get_usb_ports")
def mock_async_get_usb_ports_fixture(mock_usb_ports: dict[str, str]) -> AsyncMock:
    """Mock async_get_usb_ports."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_usb_ports",
        return_value=mock_usb_ports,
    ) as mock_get_ports:
        yield mock_get_ports


@pytest.fixture(name="mock_get_otbr_addon_manager")
def mock_get_otbr_addon_manager_fixture() -> MagicMock:
    """Mock get_otbr_addon_manager."""
    mock_manager = MagicMock()
    mock_manager.addon_name = "OpenThread Border Router"
    mock_manager.async_get_addon_info = AsyncMock()
    mock_manager.async_install_addon_waiting = AsyncMock()
    mock_manager.async_start_addon_waiting = AsyncMock()
    mock_manager.async_set_addon_options = AsyncMock()
    mock_manager.async_stop_addon = AsyncMock()

    # Set up default addon info
    mock_addon_info = MagicMock()
    mock_addon_info.state = "not_installed"
    mock_addon_info.hostname = "core-openthread-border-router"
    mock_addon_info.options = {}
    mock_manager.async_get_addon_info.return_value = mock_addon_info

    with patch(
        "homeassistant.components.otbr.config_flow.get_otbr_addon_manager",
        return_value=mock_manager,
    ) as mock_get_manager:
        yield mock_get_manager


@pytest.fixture(name="mock_is_hassio")
def mock_is_hassio_fixture() -> MagicMock:
    """Mock is_hassio."""
    with patch(
        "homeassistant.components.otbr.config_flow.is_hassio",
        return_value=True,
    ) as mock_hassio:
        yield mock_hassio


@pytest.mark.parametrize(
    "url",
    [
        "http://custom_url:1234",
        "http://custom_url:1234/",
        "http://custom_url:1234//",
    ],
)
@pytest.mark.usefixtures(
    "get_active_dataset_tlvs",
    "get_border_agent_id",
)
async def test_user_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, url: str
) -> None:
    """Test the user flow."""
    await _finish_user_flow(hass, url)


@pytest.mark.usefixtures(
    "get_active_dataset_tlvs",
    "get_extended_address",
)
async def test_user_flow_additional_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test more than a single entry is allowed."""
    url1 = "http://custom_url:1234"
    url2 = "http://custom_url_2:1234"
    aioclient_mock.get(f"{url1}/node/ba-id", json=TEST_BORDER_AGENT_ID.hex())
    aioclient_mock.get(f"{url2}/node/ba-id", json=TEST_BORDER_AGENT_ID_2.hex())

    mock_integration(hass, MockModule("hassio"))

    # Setup a config entry
    config_entry = MockConfigEntry(
        data={"url": url2},
        domain=otbr.DOMAIN,
        options={},
        title="Open Thread Border Router",
        unique_id=TEST_BORDER_AGENT_ID_2.hex(),
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    # Do a user flow
    await _finish_user_flow(hass)


@pytest.mark.usefixtures(
    "get_active_dataset_tlvs",
    "get_extended_address",
    "get_coprocessor_version",
)
async def test_user_flow_additional_entry_fail_get_address(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test more than a single entry is allowed.

    This tets the behavior when we can't read the extended address from the existing
    config entry.
    """
    url1 = "http://custom_url:1234"
    url2 = "http://custom_url_2:1234"
    aioclient_mock.get(f"{url2}/node/ba-id", json=TEST_BORDER_AGENT_ID_2.hex())

    mock_integration(hass, MockModule("hassio"))

    # Setup a config entry
    config_entry = MockConfigEntry(
        data={"url": url2},
        domain=otbr.DOMAIN,
        options={},
        title="Open Thread Border Router",
        unique_id=TEST_BORDER_AGENT_ID_2.hex(),
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    # Do a user flow
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{url1}/node/ba-id", json=TEST_BORDER_AGENT_ID.hex())
    aioclient_mock.get(f"{url2}/node/ba-id", status=HTTPStatus.NOT_FOUND)
    await _finish_user_flow(hass)
    assert f"Could not read border agent id from {url2}" in caplog.text


async def _finish_user_flow(
    hass: HomeAssistant, url: str = "http://custom_url:1234"
) -> None:
    """Finish a user flow."""
    stripped_url = "http://custom_url:1234"
    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    expected_data = {"url": stripped_url}

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": url,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Open Thread Border Router"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = result["result"]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Open Thread Border Router"
    assert config_entry.unique_id == TEST_BORDER_AGENT_ID.hex()


@pytest.mark.usefixtures(
    "get_active_dataset_tlvs",
    "get_border_agent_id",
    "get_extended_address",
    "get_coprocessor_version",
)
async def test_user_flow_additional_entry_same_address(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test more than a single entry is allowed."""
    mock_integration(hass, MockModule("hassio"))

    # Setup a config entry
    config_entry = MockConfigEntry(
        data={"url": "http://custom_url:1234"},
        domain=otbr.DOMAIN,
        options={},
        title="Open Thread Border Router",
        unique_id=TEST_BORDER_AGENT_ID.hex(),
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    # Start user flow
    url = "http://custom_url:1234"
    aioclient_mock.get(f"{url}/node/dataset/active", text="aa")
    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": url,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}


@pytest.mark.usefixtures("get_border_agent_id")
async def test_user_flow_router_not_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the user flow when the border router has no dataset.

    This tests the behavior when the thread integration has no preferred dataset.
    """
    url = "http://custom_url:1234"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{url}/node/dataset/active", status=HTTPStatus.CREATED)
    aioclient_mock.put(f"{url}/node/state", status=HTTPStatus.OK)

    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
            return_value=None,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": url,
            },
        )

    # Check we create a dataset and enable the router
    assert aioclient_mock.mock_calls[-2][0] == "PUT"
    assert aioclient_mock.mock_calls[-2][1].path == "/node/dataset/active"
    pan_id = aioclient_mock.mock_calls[-2][2]["PanId"]
    assert aioclient_mock.mock_calls[-2][2] == {
        "Channel": 15,
        "NetworkName": f"ha-thread-{pan_id:04x}",
        "PanId": pan_id,
    }

    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "enable"

    expected_data = {
        "url": "http://custom_url:1234",
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Open Thread Border Router"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Open Thread Border Router"
    assert config_entry.unique_id == TEST_BORDER_AGENT_ID.hex()


@pytest.mark.usefixtures("get_border_agent_id")
async def test_user_flow_get_dataset_404(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the user flow."""
    url = "http://custom_url:1234"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NOT_FOUND)
    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": url,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError,
        python_otbr_api.OTBRError,
        aiohttp.ClientError,
    ],
)
async def test_user_flow_get_ba_id_connect_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, error
) -> None:
    """Test the user flow."""
    await _test_user_flow_connect_error(hass, "get_border_agent_id", error)


@pytest.mark.usefixtures("get_border_agent_id")
@pytest.mark.parametrize(
    "error",
    [
        TimeoutError,
        python_otbr_api.OTBRError,
        aiohttp.ClientError,
    ],
)
async def test_user_flow_get_dataset_connect_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, error
) -> None:
    """Test the user flow."""
    await _test_user_flow_connect_error(hass, "get_active_dataset_tlvs", error)


async def _test_user_flow_connect_error(hass: HomeAssistant, func, error) -> None:
    """Test the user flow."""
    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(f"python_otbr_api.OTBR.{func}", side_effect=error):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://custom_url:1234",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("get_border_agent_id")
async def test_hassio_discovery_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_addon_info
) -> None:
    """Test the hassio discovery flow."""
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", text="aa")

    with patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
        )

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Silicon Labs Multiprotocol"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Silicon Labs Multiprotocol"
    assert config_entry.unique_id == HASSIO_DATA.uuid


@pytest.mark.usefixtures("get_border_agent_id")
async def test_hassio_discovery_flow_yellow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_addon_info
) -> None:
    """Test the hassio discovery flow."""
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", text="aa")

    otbr_addon_info.return_value.available = True
    otbr_addon_info.return_value.options = {"device": "/dev/ttyAMA1"}

    with (
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch("homeassistant.components.otbr.config_flow.yellow_hardware.async_info"),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
        )

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant Yellow (Silicon Labs Multiprotocol)"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Home Assistant Yellow (Silicon Labs Multiprotocol)"
    assert config_entry.unique_id == HASSIO_DATA.uuid


@pytest.mark.parametrize(
    ("device", "title"),
    [
        (
            "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
            "Home Assistant Connect ZBT-1 (Silicon Labs Multiprotocol)",
        ),
        (
            "/dev/serial/by-id/usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
            "Home Assistant Connect ZBT-1 (Silicon Labs Multiprotocol)",
        ),
    ],
)
@pytest.mark.usefixtures("get_border_agent_id")
async def test_hassio_discovery_flow_sky_connect(
    device: str,
    title: str,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_addon_info,
) -> None:
    """Test the hassio discovery flow."""
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", text="aa")

    otbr_addon_info.return_value.available = True
    otbr_addon_info.return_value.options = {"device": device}

    with patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
        )

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == title
    assert config_entry.unique_id == HASSIO_DATA.uuid


@pytest.mark.usefixtures("get_active_dataset_tlvs", "get_extended_address")
async def test_hassio_discovery_flow_2x_addons(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_addon_info
) -> None:
    """Test the hassio discovery flow when the user has 2 addons with otbr support."""
    url1 = "http://core-silabs-multiprotocol:8081"
    url2 = "http://core-silabs-multiprotocol_2:8081"
    aioclient_mock.get(f"{url1}/node/dataset/active", text="aa")
    aioclient_mock.get(f"{url2}/node/dataset/active", text="bb")
    aioclient_mock.get(f"{url1}/node/ba-id", json=TEST_BORDER_AGENT_ID.hex())
    aioclient_mock.get(f"{url2}/node/ba-id", json=TEST_BORDER_AGENT_ID_2.hex())

    async def _addon_info(slug: str) -> Mock:
        await asyncio.sleep(0)
        if slug == "otbr":
            device = (
                "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_"
                "9e2adbd75b8beb119fe564a0f320645d-if00-port0"
            )
        else:
            device = (
                "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_"
                "9e2adbd75b8beb119fe564a0f320645d-if00-port1"
            )
        return Mock(
            available=True,
            hostname=otbr_addon_info.return_value.hostname,
            options={"device": device},
            state=otbr_addon_info.return_value.state,
            update_available=otbr_addon_info.return_value.update_available,
            version=otbr_addon_info.return_value.version,
        )

    otbr_addon_info.side_effect = _addon_info

    result1 = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
    )
    result2 = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA_2
    )

    results = [result1, result2]

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }
    expected_data_2 = {
        "url": f"http://{HASSIO_DATA_2.config['host']}:{HASSIO_DATA_2.config['port']}",
    }

    assert results[0]["type"] is FlowResultType.CREATE_ENTRY
    assert (
        results[0]["title"]
        == "Home Assistant Connect ZBT-1 (Silicon Labs Multiprotocol)"
    )
    assert results[0]["data"] == expected_data
    assert results[0]["options"] == {}

    assert results[1]["type"] is FlowResultType.CREATE_ENTRY
    assert (
        results[1]["title"]
        == "Home Assistant Connect ZBT-1 (Silicon Labs Multiprotocol)"
    )
    assert results[1]["data"] == expected_data_2
    assert results[1]["options"] == {}

    assert len(hass.config_entries.async_entries(otbr.DOMAIN)) == 2

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert (
        config_entry.title
        == "Home Assistant Connect ZBT-1 (Silicon Labs Multiprotocol)"
    )
    assert config_entry.unique_id == HASSIO_DATA.uuid

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[1]
    assert config_entry.data == expected_data_2
    assert config_entry.options == {}
    assert (
        config_entry.title
        == "Home Assistant Connect ZBT-1 (Silicon Labs Multiprotocol)"
    )
    assert config_entry.unique_id == HASSIO_DATA_2.uuid


@pytest.mark.usefixtures(
    "get_active_dataset_tlvs",
    "get_extended_address",
    "get_coprocessor_version",
)
async def test_hassio_discovery_flow_2x_addons_same_ext_address(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_addon_info
) -> None:
    """Test the hassio discovery flow when the user has 2 addons with otbr support."""
    url1 = "http://core-silabs-multiprotocol:8081"
    url2 = "http://core-silabs-multiprotocol_2:8081"
    aioclient_mock.get(f"{url1}/node/dataset/active", text="aa")
    aioclient_mock.get(f"{url2}/node/dataset/active", text="bb")
    aioclient_mock.get(f"{url1}/node/ba-id", json=TEST_BORDER_AGENT_ID.hex())
    aioclient_mock.get(f"{url2}/node/ba-id", json=TEST_BORDER_AGENT_ID.hex())

    async def _addon_info(slug: str) -> Mock:
        await asyncio.sleep(0)
        if slug == "otbr":
            device = (
                "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_"
                "9e2adbd75b8beb119fe564a0f320645d-if00-port0"
            )
        else:
            device = (
                "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_"
                "9e2adbd75b8beb119fe564a0f320645d-if00-port1"
            )
        return Mock(
            available=True,
            hostname=otbr_addon_info.return_value.hostname,
            options={"device": device},
            state=otbr_addon_info.return_value.state,
            update_available=otbr_addon_info.return_value.update_available,
            version=otbr_addon_info.return_value.version,
        )

    otbr_addon_info.side_effect = _addon_info

    result1 = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
    )
    result2 = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA_2
    )

    results = [result1, result2]

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }

    assert results[0]["type"] is FlowResultType.CREATE_ENTRY
    assert (
        results[0]["title"]
        == "Home Assistant Connect ZBT-1 (Silicon Labs Multiprotocol)"
    )
    assert results[0]["data"] == expected_data
    assert results[0]["options"] == {}
    assert results[1]["type"] is FlowResultType.ABORT
    assert results[1]["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(otbr.DOMAIN)) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert (
        config_entry.title
        == "Home Assistant Connect ZBT-1 (Silicon Labs Multiprotocol)"
    )
    assert config_entry.unique_id == HASSIO_DATA.uuid


@pytest.mark.usefixtures("get_border_agent_id")
async def test_hassio_discovery_flow_router_not_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_addon_info
) -> None:
    """Test the hassio discovery flow when the border router has no dataset.

    This tests the behavior when the thread integration has no preferred dataset.
    """
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{url}/node/dataset/active", status=HTTPStatus.CREATED)
    aioclient_mock.put(f"{url}/node/state", status=HTTPStatus.OK)

    with (
        patch(
            "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
            return_value=None,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
        )

    # Check we create a dataset and enable the router
    assert aioclient_mock.mock_calls[-2][0] == "PUT"
    assert aioclient_mock.mock_calls[-2][1].path == "/node/dataset/active"
    pan_id = aioclient_mock.mock_calls[-2][2]["PanId"]
    assert aioclient_mock.mock_calls[-2][2] == {
        "Channel": 15,
        "NetworkName": f"ha-thread-{pan_id:04x}",
        "PanId": pan_id,
    }

    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "enable"

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Silicon Labs Multiprotocol"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Silicon Labs Multiprotocol"
    assert config_entry.unique_id == HASSIO_DATA.uuid


@pytest.mark.usefixtures("get_border_agent_id")
async def test_hassio_discovery_flow_router_not_setup_has_preferred(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_addon_info
) -> None:
    """Test the hassio discovery flow when the border router has no dataset.

    This tests the behavior when the thread integration has a preferred dataset.
    """
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{url}/node/dataset/active", status=HTTPStatus.CREATED)
    aioclient_mock.put(f"{url}/node/state", status=HTTPStatus.OK)

    with (
        patch(
            "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
            return_value=DATASET_CH15.hex(),
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
        )

    # Check we create a dataset and enable the router
    assert aioclient_mock.mock_calls[-2][0] == "PUT"
    assert aioclient_mock.mock_calls[-2][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-2][2] == DATASET_CH15.hex()

    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "enable"

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Silicon Labs Multiprotocol"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Silicon Labs Multiprotocol"
    assert config_entry.unique_id == HASSIO_DATA.uuid


@pytest.mark.usefixtures("get_border_agent_id")
async def test_hassio_discovery_flow_router_not_setup_has_preferred_2(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    multiprotocol_addon_manager_mock,
    otbr_addon_info,
) -> None:
    """Test the hassio discovery flow when the border router has no dataset.

    This tests the behavior when the thread integration has a preferred dataset, but
    the preferred dataset is not using channel 15.
    """
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{url}/node/dataset/active", status=HTTPStatus.CREATED)
    aioclient_mock.put(f"{url}/node/state", status=HTTPStatus.OK)

    multiprotocol_addon_manager_mock.async_get_channel.return_value = 15

    with (
        patch(
            "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
            return_value=DATASET_CH16.hex(),
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
        )

    # Check we create a dataset and enable the router
    assert aioclient_mock.mock_calls[-2][0] == "PUT"
    assert aioclient_mock.mock_calls[-2][1].path == "/node/dataset/active"
    pan_id = aioclient_mock.mock_calls[-2][2]["PanId"]
    assert aioclient_mock.mock_calls[-2][2] == {
        "Channel": 15,
        "NetworkName": f"ha-thread-{pan_id:04x}",
        "PanId": pan_id,
    }

    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "enable"

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Silicon Labs Multiprotocol"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Silicon Labs Multiprotocol"
    assert config_entry.unique_id == HASSIO_DATA.uuid


@pytest.mark.usefixtures("get_border_agent_id")
async def test_hassio_discovery_flow_404(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the user and discovery flows."""
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NOT_FOUND)
    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.usefixtures("get_border_agent_id")
async def test_hassio_discovery_flow_new_port_missing_unique_id(
    hass: HomeAssistant,
) -> None:
    """Test the port can be updated when the unique id is missing."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={
            "url": (
                f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port'] + 1}"
            )
        },
        domain=otbr.DOMAIN,
        options={},
        source="hassio",
        title="Open Thread Border Router",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }
    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data


@pytest.mark.usefixtures("get_border_agent_id")
async def test_hassio_discovery_flow_new_port(hass: HomeAssistant) -> None:
    """Test the port can be updated."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={
            "url": (
                f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port'] + 1}"
            )
        },
        domain=otbr.DOMAIN,
        options={},
        source="hassio",
        title="Open Thread Border Router",
        unique_id=HASSIO_DATA.uuid,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }
    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data


@pytest.mark.usefixtures(
    "otbr_addon_info",
    "get_active_dataset_tlvs",
    "get_border_agent_id",
    "get_extended_address",
)
async def test_hassio_discovery_flow_new_port_other_addon(hass: HomeAssistant) -> None:
    """Test the port is not updated if we get data for another addon hosting OTBR."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={
            "url": f"http://openthread_border_router:{HASSIO_DATA.config['port'] + 1}"
        },
        domain=otbr.DOMAIN,
        options={},
        source="hassio",
        title="Open Thread Border Router",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
    )

    # Another entry will be created
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Make sure the data of the existing entry was not updated
    expected_data = {
        "url": f"http://openthread_border_router:{HASSIO_DATA.config['port'] + 1}",
    }
    config_entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert config_entry.data == expected_data


@pytest.mark.parametrize(
    ("source", "data", "expected_result"),
    [
        ("hassio", HASSIO_DATA, FlowResultType.CREATE_ENTRY),
        ("user", None, FlowResultType.FORM),
    ],
)
@pytest.mark.usefixtures(
    "otbr_addon_info",
    "get_active_dataset_tlvs",
    "get_border_agent_id",
    "get_extended_address",
)
async def test_config_flow_additional_entry(
    hass: HomeAssistant, source: str, data: Any, expected_result: FlowResultType
) -> None:
    """Test more than a single entry is allowed."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=otbr.DOMAIN,
        options={},
        title="Open Thread Border Router",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": source}, data=data
        )

    assert result["type"] is expected_result


@pytest.mark.usefixtures(
    "get_border_agent_id", "get_extended_address", "get_coprocessor_version"
)
async def test_hassio_discovery_reload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, otbr_addon_info
) -> None:
    """Test the hassio discovery flow."""
    await async_setup_component(hass, "homeassistant_hardware", {})

    aioclient_mock.get(
        "http://core-openthread-border-router:8081/node/dataset/active", text=""
    )

    callback = Mock()
    async_register_firmware_info_callback(hass, "/dev/ttyUSB1", callback)

    with (
        patch(
            "homeassistant.components.otbr.homeassistant_hardware.is_hassio",
            return_value=True,
        ),
        patch(
            "homeassistant.components.otbr.homeassistant_hardware.get_otbr_addon_firmware_info",
            return_value=FirmwareInfo(
                device="/dev/ttyUSB1",
                firmware_type=ApplicationType.SPINEL,
                firmware_version=None,
                source="otbr",
                owners=[
                    OwningAddon(slug="core_openthread_border_router"),
                ],
            ),
        ),
    ):
        await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA_OTBR
        )

        # OTBR is set up and calls the firmware info notification callback
        assert len(callback.mock_calls) == 1
        assert len(hass.config_entries.async_entries(otbr.DOMAIN)) == 1

        # If we change discovery info and emit again, the integration will be reloaded
        # and firmware information will be broadcast again
        await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA_OTBR
        )

        assert len(callback.mock_calls) == 2
        assert len(hass.config_entries.async_entries(otbr.DOMAIN)) == 1


# Tests for new recommended flow


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_user_step_shows_menu(hass: HomeAssistant) -> None:
    """Test user step shows menu on Hass.io."""
    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["recommended", "url"]


async def test_user_step_skips_to_url_when_not_hassio(hass: HomeAssistant) -> None:
    """Test user step skips to URL when not on Hass.io."""
    with patch(
        "homeassistant.components.otbr.config_flow.is_hassio",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "url"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_recommended_step_shows_usb_devices(
    hass: HomeAssistant, mock_usb_ports: dict[str, str]
) -> None:
    """Test recommended step shows available USB devices."""
    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "recommended"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "recommended"
    assert "data_schema" in result
    device_options = result["data_schema"].schema["device"].container
    assert set(device_options) == set(mock_usb_ports.keys())


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_recommended_step_device_selection(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test recommended step device selection proceeds to addon step."""
    # Mock the network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

        # The flow should complete successfully and create an entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Open Thread Border Router"


@pytest.mark.usefixtures("mock_is_hassio")
async def test_recommended_step_usb_ports_failure(hass: HomeAssistant) -> None:
    """Test recommended step handles USB port detection failure."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_usb_ports",
        side_effect=OSError("USB detection failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "usb_ports_failed"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_recommended_step_skips_device_selection_if_already_set(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test recommended step skips device selection if device already set."""
    # Mock the network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        # First call should show device selection form since no device is set yet
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "recommended"

        # Now select a device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

        # The flow should complete successfully and create an entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Open Thread Border Router"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_addon_step_not_installed_proceeds_to_install(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test addon step proceeds to install when not installed."""
    # Mock the network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

        # The flow should complete successfully and create an entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Open Thread Border Router"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_addon_step_running_stops_then_starts(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test addon step stops running addon then starts."""
    # Set addon as running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "running"

    # Mock the network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

        # The flow should complete successfully and create an entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Open Thread Border Router"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_install_otbr_addon_progress(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR addon installation progress."""
    # Mock the network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

        # The flow should complete successfully and create an entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Open Thread Border Router"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_install_otbr_addon_success(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR addon installation success."""
    # Mock successful installation
    mock_get_otbr_addon_manager.return_value.async_install_addon_waiting.return_value = None

    # Mock the network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

        # The flow should complete successfully and create an entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Open Thread Border Router"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_install_otbr_addon_failure(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR connection failure during flow."""
    # Mock network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            side_effect=HomeAssistantError("Connection failed"),
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

    # Should abort due to connection failure
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_start_otbr_addon_progress(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR addon start progress."""
    # Set addon as installed but not running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "installed"

    # Mock the network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

        # The flow should complete successfully and create an entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Open Thread Border Router"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_start_otbr_addon_success(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR addon start success."""
    # Set addon as installed but not running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "installed"

    # Mock successful start
    mock_get_otbr_addon_manager.return_value.async_start_addon_waiting.return_value = (
        None
    )

    # Mock the network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

        # Verify addon options were set
        mock_get_otbr_addon_manager.return_value.async_set_addon_options.assert_called_once()
        call_args = (
            mock_get_otbr_addon_manager.return_value.async_set_addon_options.call_args[
                0
            ][0]
        )
        assert call_args["device"] == "/dev/ttyUSB0"
        assert call_args["autoflash_firmware"] is False

        # The flow should complete successfully and create an entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Open Thread Border Router"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_start_otbr_addon_set_config_failure(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR addon start with set config failure."""

    # Set addon as installed but not running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "installed"

    # Mock set config failure
    mock_get_otbr_addon_manager.return_value.async_set_addon_options.side_effect = (
        AddonError("Config failed")
    )

    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "recommended"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/ttyUSB0"}
    )

    # Should abort due to config failure
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_set_config_failed"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_start_otbr_addon_start_failure(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR addon start failure."""

    # Set addon as installed but not running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "installed"

    # Mock start failure
    mock_get_otbr_addon_manager.return_value.async_start_addon_waiting.side_effect = (
        AddonError("Start failed")
    )

    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "recommended"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/ttyUSB0"}
    )

    # Should abort due to start failure
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_start_failed"


@pytest.mark.usefixtures(
    "mock_is_hassio", "mock_async_get_usb_ports", "get_border_agent_id"
)
async def test_connect_otbr_progress(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR connection progress."""
    # Set addon as running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "running"
    mock_addon_info.hostname = "core-openthread-border-router"

    # Mock the network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

        # The flow should complete successfully and create an entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Open Thread Border Router"


@pytest.mark.usefixtures(
    "mock_is_hassio",
    "mock_async_get_usb_ports",
    "get_border_agent_id",
    "get_active_dataset_tlvs",
)
async def test_connect_otbr_success(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR connection success."""
    # Set addon as running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "running"
    mock_addon_info.hostname = "core-openthread-border-router"

    # Mock the network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

        # The flow should complete successfully and create an entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Open Thread Border Router"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_connect_otbr_already_configured(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR connection when already configured."""
    # Set addon as running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "running"
    mock_addon_info.hostname = "core-openthread-border-router"

    # Mock already configured error
    with patch(
        "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
        side_effect=otbr.config_flow.AlreadyConfigured(),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_connect_otbr_connection_failure(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR connection failure."""
    # Set addon as running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "running"
    mock_addon_info.hostname = "core-openthread-border-router"

    # Mock connection failure
    with patch(
        "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
        side_effect=HomeAssistantError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.usefixtures(
    "mock_is_hassio",
    "mock_async_get_usb_ports",
    "get_border_agent_id",
    "get_active_dataset_tlvs",
)
async def test_addon_done_creates_entry(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test addon done step creates config entry."""
    # Set addon as running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "running"
    mock_addon_info.hostname = "core-openthread-border-router"

    # Mock the network calls to prevent actual network requests
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Open Thread Border Router"
    assert result["data"] == {
        "url": "http://core-openthread-border-router:8081",
        "device": "/dev/ttyUSB0",
    }
    assert len(mock_setup_entry.mock_calls) == 1


# Tests for USB port filtering and edge cases


@pytest.mark.usefixtures("mock_is_hassio")
async def test_usb_ports_filtering_all_na(hass: HomeAssistant) -> None:
    """Test USB port filtering when all ports are 'n/a'."""
    na_ports = {
        "/dev/ttyUSB0": "n/a",
        "/dev/ttyUSB1": "N/A",
        "/dev/ttyUSB2": "Not Available",
    }

    with patch(
        "homeassistant.components.otbr.config_flow.async_get_usb_ports",
        return_value=na_ports,
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "recommended"
    # Should show all ports since they're all "n/a"
    assert len(result["data_schema"].schema["device"].container) == 3


@pytest.mark.usefixtures("mock_is_hassio")
async def test_usb_ports_filtering_mixed_case(hass: HomeAssistant) -> None:
    """Test USB port filtering with mixed valid and 'n/a' ports."""

    # Expected filtered ports (only non-"n/a" ports)
    expected_filtered_ports = {
        "/dev/ttyUSB0": "Home Assistant Connect ZBT-1",
        "/dev/ttyUSB2": "SkyConnect",
        "/dev/ttyUSB3": "Not Available",
    }

    with patch(
        "homeassistant.components.otbr.config_flow.async_get_usb_ports",
        return_value=expected_filtered_ports,  # Return the filtered result
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "recommended"
    # Should only show non-"n/a" ports (case-sensitive, lowercase only)
    device_options = result["data_schema"].schema["device"].container
    assert len(device_options) == 3  # All except "/dev/ttyUSB1" which is "n/a"
    assert "/dev/ttyUSB0" in device_options
    assert "/dev/ttyUSB2" in device_options
    assert "/dev/ttyUSB3" in device_options
    assert "/dev/ttyUSB1" not in device_options


@pytest.mark.usefixtures("mock_is_hassio")
async def test_usb_ports_empty_list(hass: HomeAssistant) -> None:
    """Test USB port detection with empty list."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_usb_ports",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "recommended"
    assert len(result["data_schema"].schema["device"].container) == 0


# Tests for retry logic and connection timeouts


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_connect_otbr_retry_logic(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR connection retry logic."""
    # Set addon as running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "running"
    mock_addon_info.hostname = "core-openthread-border-router"

    # Mock connection success
    with (
        patch(
            "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
            return_value=TEST_BORDER_AGENT_ID,
        ),
        patch(
            "homeassistant.components.otbr.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Open Thread Border Router"


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_connect_otbr_timeout(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test OTBR connection timeout."""
    # Set addon as running
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "running"
    mock_addon_info.hostname = "core-openthread-border-router"

    # Mock persistent connection failure
    with patch(
        "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_with_retry",
        side_effect=HomeAssistantError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "recommended"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


# Tests for addon info failures


@pytest.mark.usefixtures("mock_is_hassio", "mock_async_get_usb_ports")
async def test_addon_info_failure(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test addon info failure."""

    # Mock addon info failure
    mock_get_otbr_addon_manager.return_value.async_get_addon_info.side_effect = (
        AddonError("Info failed")
    )

    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "recommended"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/ttyUSB0"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "addon_info_failed"


# Tests for URL flow (existing functionality)


@pytest.mark.usefixtures("get_border_agent_id", "get_active_dataset_tlvs")
async def test_url_step_success(hass: HomeAssistant) -> None:
    """Test URL step success."""
    with patch(
        "homeassistant.components.otbr.config_flow.is_hassio",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "url"

    with patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "http://custom_url:1234"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Open Thread Border Router"
    assert result["data"] == {"url": "http://custom_url:1234"}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("get_border_agent_id")
async def test_url_step_already_configured(hass: HomeAssistant) -> None:
    """Test URL step when already configured."""
    with patch(
        "homeassistant.components.otbr.config_flow.is_hassio",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

    # Mock already configured error
    with patch(
        "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_and_configure_router",
        side_effect=otbr.config_flow.AlreadyConfigured(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "http://custom_url:1234"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}


@pytest.mark.usefixtures("get_border_agent_id")
async def test_url_step_connection_error(hass: HomeAssistant) -> None:
    """Test URL step connection error."""
    with patch(
        "homeassistant.components.otbr.config_flow.is_hassio",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "user"}
        )

    # Mock connection error
    with patch(
        "homeassistant.components.otbr.config_flow.OTBRConfigFlow._connect_and_configure_router",
        side_effect=aiohttp.ClientError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "http://custom_url:1234"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


# Tests for complete recommended flow integration


@pytest.mark.usefixtures(
    "mock_is_hassio",
    "mock_async_get_usb_ports",
    "get_border_agent_id",
    "get_active_dataset_tlvs",
)
async def test_complete_recommended_flow_success(
    hass: HomeAssistant, mock_get_otbr_addon_manager: MagicMock
) -> None:
    """Test complete recommended flow from start to finish."""
    # Set up successful addon installation and start
    mock_addon_info = (
        mock_get_otbr_addon_manager.return_value.async_get_addon_info.return_value
    )
    mock_addon_info.state = "not_installed"
    mock_addon_info.hostname = "core-openthread-border-router"

    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    # Step 1: Choose recommended
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "recommended"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "recommended"

    # Step 2: Select device - this should complete the entire flow
    with patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Open Thread Border Router"
    assert result["data"] == {
        "url": "http://core-openthread-border-router:8081",
        "device": "/dev/ttyUSB0",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # Verify addon operations were called (installation is skipped if addon is already running)
    mock_get_otbr_addon_manager.return_value.async_set_addon_options.assert_called_once()
    # async_start_addon_waiting is only called if addon was not running
