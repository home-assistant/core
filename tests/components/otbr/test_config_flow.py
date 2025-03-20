"""Test the Open Thread Border Router config flow."""

import asyncio
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
import python_otbr_api

from homeassistant.components import otbr
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
            "Home Assistant SkyConnect (Silicon Labs Multiprotocol)",
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
        results[0]["title"] == "Home Assistant SkyConnect (Silicon Labs Multiprotocol)"
    )
    assert results[0]["data"] == expected_data
    assert results[0]["options"] == {}

    assert results[1]["type"] is FlowResultType.CREATE_ENTRY
    assert (
        results[1]["title"] == "Home Assistant SkyConnect (Silicon Labs Multiprotocol)"
    )
    assert results[1]["data"] == expected_data_2
    assert results[1]["options"] == {}

    assert len(hass.config_entries.async_entries(otbr.DOMAIN)) == 2

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert (
        config_entry.title == "Home Assistant SkyConnect (Silicon Labs Multiprotocol)"
    )
    assert config_entry.unique_id == HASSIO_DATA.uuid

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[1]
    assert config_entry.data == expected_data_2
    assert config_entry.options == {}
    assert (
        config_entry.title == "Home Assistant SkyConnect (Silicon Labs Multiprotocol)"
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
        results[0]["title"] == "Home Assistant SkyConnect (Silicon Labs Multiprotocol)"
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
        config_entry.title == "Home Assistant SkyConnect (Silicon Labs Multiprotocol)"
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
