"""Test the Open Thread Border Router config flow."""
import asyncio
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest
import python_otbr_api

from homeassistant.components import hassio, otbr
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import DATASET_CH15, DATASET_CH16

from tests.common import MockConfigEntry, MockModule, mock_integration
from tests.test_util.aiohttp import AiohttpClientMocker

HASSIO_DATA = hassio.HassioServiceInfo(
    config={"host": "core-silabs-multiprotocol", "port": 8081},
    name="Silicon Labs Multiprotocol",
    slug="otbr",
    uuid="12345",
)
HASSIO_DATA_2 = hassio.HassioServiceInfo(
    config={"host": "core-silabs-multiprotocol_2", "port": 8082},
    name="Silicon Labs Multiprotocol",
    slug="other_addon",
    uuid="23456",
)


@pytest.fixture(name="addon_info")
def addon_info_fixture():
    """Mock Supervisor add-on info."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_addon_info",
    ) as addon_info:
        addon_info.return_value = {
            "available": True,
            "hostname": None,
            "options": {},
            "state": None,
            "update_available": False,
            "version": None,
        }
        yield addon_info


async def test_user_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the user flow."""
    url = "http://custom_url:1234"
    aioclient_mock.get(f"{url}/node/dataset/active", text="aa")
    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    expected_data = {"url": url}

    assert result["type"] == FlowResultType.FORM
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
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Open Thread Border Router"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Open Thread Border Router"
    assert config_entry.unique_id == otbr.DOMAIN


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
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=None,
    ), patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": url,
            },
        )

    # Check we create a dataset and enable the router
    assert aioclient_mock.mock_calls[-2][0] == "PUT"
    assert aioclient_mock.mock_calls[-2][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-2][2] == {
        "Channel": 15,
        "NetworkName": "home-assistant",
    }

    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "enable"

    expected_data = {
        "url": "http://custom_url:1234",
    }

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Open Thread Border Router"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Open Thread Border Router"
    assert config_entry.unique_id == otbr.DOMAIN


async def test_user_flow_404(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the user flow."""
    url = "http://custom_url:1234"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NOT_FOUND)
    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": url,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    "error",
    [
        asyncio.TimeoutError,
        python_otbr_api.OTBRError,
        aiohttp.ClientError,
    ],
)
async def test_user_flow_connect_error(hass: HomeAssistant, error) -> None:
    """Test the user flow."""
    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch("python_otbr_api.OTBR.get_active_dataset_tlvs", side_effect=error):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "http://custom_url:1234",
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_hassio_discovery_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_info
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

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Silicon Labs Multiprotocol"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Silicon Labs Multiprotocol"
    assert config_entry.unique_id == HASSIO_DATA.uuid


async def test_hassio_discovery_flow_yellow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_info
) -> None:
    """Test the hassio discovery flow."""
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", text="aa")

    addon_info.return_value = {
        "available": True,
        "hostname": None,
        "options": {"device": "/dev/ttyAMA1"},
        "state": None,
        "update_available": False,
        "version": None,
    }

    with patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.otbr.config_flow.yellow_hardware.async_info"
    ):
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
        )

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant Yellow (Silicon Labs Multiprotocol)"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Home Assistant Yellow (Silicon Labs Multiprotocol)"
    assert config_entry.unique_id == HASSIO_DATA.uuid


async def test_hassio_discovery_flow_sky_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_info
) -> None:
    """Test the hassio discovery flow."""
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", text="aa")

    addon_info.return_value = {
        "available": True,
        "hostname": None,
        "options": {
            "device": (
                "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_"
                "9e2adbd75b8beb119fe564a0f320645d-if00-port0"
            )
        },
        "state": None,
        "update_available": False,
        "version": None,
    }

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

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant SkyConnect (Silicon Labs Multiprotocol)"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert (
        config_entry.title == "Home Assistant SkyConnect (Silicon Labs Multiprotocol)"
    )
    assert config_entry.unique_id == HASSIO_DATA.uuid


async def test_hassio_discovery_flow_2x_addons(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_info
) -> None:
    """Test the hassio discovery flow when the user has 2 addons with otbr support."""
    url1 = "http://core-silabs-multiprotocol:8081"
    url2 = "http://core-silabs-multiprotocol_2:8081"
    aioclient_mock.get(f"{url1}/node/dataset/active", text="aa")
    aioclient_mock.get(f"{url2}/node/dataset/active", text="bb")

    async def _addon_info(hass, slug):
        await asyncio.sleep(0)
        if slug == "otbr":
            return {
                "available": True,
                "hostname": None,
                "options": {
                    "device": (
                        "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_"
                        "9e2adbd75b8beb119fe564a0f320645d-if00-port0"
                    )
                },
                "state": None,
                "update_available": False,
                "version": None,
            }
        return {
            "available": True,
            "hostname": None,
            "options": {
                "device": (
                    "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_"
                    "9e2adbd75b8beb119fe564a0f320645d-if00-port1"
                )
            },
            "state": None,
            "update_available": False,
            "version": None,
        }

    addon_info.side_effect = _addon_info

    with patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        results = await asyncio.gather(
            hass.config_entries.flow.async_init(
                otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
            ),
            hass.config_entries.flow.async_init(
                otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA_2
            ),
        )

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }

    assert results[0]["type"] == FlowResultType.CREATE_ENTRY
    assert (
        results[0]["title"] == "Home Assistant SkyConnect (Silicon Labs Multiprotocol)"
    )
    assert results[0]["data"] == expected_data
    assert results[0]["options"] == {}
    assert results[1]["type"] == FlowResultType.ABORT
    assert results[1]["reason"] == "single_instance_allowed"
    assert len(hass.config_entries.async_entries(otbr.DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert (
        config_entry.title == "Home Assistant SkyConnect (Silicon Labs Multiprotocol)"
    )
    assert config_entry.unique_id == HASSIO_DATA.uuid


async def test_hassio_discovery_flow_router_not_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_info
) -> None:
    """Test the hassio discovery flow when the border router has no dataset.

    This tests the behavior when the thread integration has no preferred dataset.
    """
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{url}/node/dataset/active", status=HTTPStatus.CREATED)
    aioclient_mock.put(f"{url}/node/state", status=HTTPStatus.OK)

    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=None,
    ), patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
        )

    # Check we create a dataset and enable the router
    assert aioclient_mock.mock_calls[-2][0] == "PUT"
    assert aioclient_mock.mock_calls[-2][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-2][2] == {
        "Channel": 15,
        "NetworkName": "home-assistant",
    }

    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "enable"

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Silicon Labs Multiprotocol"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Silicon Labs Multiprotocol"
    assert config_entry.unique_id == HASSIO_DATA.uuid


async def test_hassio_discovery_flow_router_not_setup_has_preferred(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, addon_info
) -> None:
    """Test the hassio discovery flow when the border router has no dataset.

    This tests the behavior when the thread integration has a preferred dataset.
    """
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{url}/node/dataset/active", status=HTTPStatus.CREATED)
    aioclient_mock.put(f"{url}/node/state", status=HTTPStatus.OK)

    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=DATASET_CH15.hex(),
    ), patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Silicon Labs Multiprotocol"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Silicon Labs Multiprotocol"
    assert config_entry.unique_id == HASSIO_DATA.uuid


async def test_hassio_discovery_flow_router_not_setup_has_preferred_2(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    multiprotocol_addon_manager_mock,
    addon_info,
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

    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=DATASET_CH16.hex(),
    ), patch(
        "homeassistant.components.otbr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
        )

    # Check we create a dataset and enable the router
    assert aioclient_mock.mock_calls[-2][0] == "PUT"
    assert aioclient_mock.mock_calls[-2][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-2][2] == {
        "Channel": 15,
        "NetworkName": "home-assistant",
    }

    assert aioclient_mock.mock_calls[-1][0] == "PUT"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "enable"

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Silicon Labs Multiprotocol"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Silicon Labs Multiprotocol"
    assert config_entry.unique_id == HASSIO_DATA.uuid


async def test_hassio_discovery_flow_404(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the user and discovery flows."""
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NOT_FOUND)
    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_hassio_discovery_flow_new_port(hass: HomeAssistant) -> None:
    """Test the port can be updated."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={
            "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']+1}"
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

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
    }
    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data


async def test_hassio_discovery_flow_new_port_other_addon(hass: HomeAssistant) -> None:
    """Test the port is not updated if we get data for another addon hosting OTBR."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={"url": f"http://openthread_border_router:{HASSIO_DATA.config['port']+1}"},
        domain=otbr.DOMAIN,
        options={},
        source="hassio",
        title="Open Thread Border Router",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        otbr.DOMAIN, context={"source": "hassio"}, data=HASSIO_DATA
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"

    # Make sure the data was not updated
    expected_data = {
        "url": f"http://openthread_border_router:{HASSIO_DATA.config['port']+1}",
    }
    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data


@pytest.mark.parametrize(("source", "data"), [("hassio", HASSIO_DATA), ("user", None)])
async def test_config_flow_single_entry(
    hass: HomeAssistant, source: str, data: Any
) -> None:
    """Test only a single entry is allowed."""
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
        "homeassistant.components.homeassistant_yellow.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            otbr.DOMAIN, context={"source": source}, data=data
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    mock_setup_entry.assert_not_called()
