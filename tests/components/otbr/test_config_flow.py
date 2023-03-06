"""Test the Open Thread Border Router config flow."""
import asyncio
from http import HTTPStatus
from unittest.mock import patch

import aiohttp
import pytest
import python_otbr_api

from homeassistant.components import hassio, otbr
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import BASE_URL, DATASET_CH15, DATASET_CH16

from tests.common import MockConfigEntry, MockModule, mock_integration
from tests.test_util.aiohttp import AiohttpClientMocker

HASSIO_DATA = hassio.HassioServiceInfo(
    config={"host": "core-silabs-multiprotocol", "port": 8081},
    name="Silicon Labs Multiprotocol",
    slug="otbr",
)


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
    aioclient_mock.post(f"{url}/node/dataset/active", status=HTTPStatus.ACCEPTED)
    aioclient_mock.post(f"{url}/node/state", status=HTTPStatus.OK)

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
    assert aioclient_mock.mock_calls[-2][0] == "POST"
    assert aioclient_mock.mock_calls[-2][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-2][2] == {
        "Channel": 15,
        "NetworkName": "home-assistant",
    }

    assert aioclient_mock.mock_calls[-1][0] == "POST"
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
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
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
    assert result["title"] == "Open Thread Border Router"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(otbr.DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Open Thread Border Router"
    assert config_entry.unique_id == otbr.DOMAIN


async def test_hassio_discovery_flow_router_not_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the hassio discovery flow when the border router has no dataset.

    This tests the behavior when the thread integration has no preferred dataset.
    """
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.post(f"{url}/node/dataset/active", status=HTTPStatus.ACCEPTED)
    aioclient_mock.post(f"{url}/node/state", status=HTTPStatus.OK)

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
    assert aioclient_mock.mock_calls[-2][0] == "POST"
    assert aioclient_mock.mock_calls[-2][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-2][2] == {
        "Channel": 15,
        "NetworkName": "home-assistant",
    }

    assert aioclient_mock.mock_calls[-1][0] == "POST"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "enable"

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
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


async def test_hassio_discovery_flow_router_not_setup_has_preferred(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the hassio discovery flow when the border router has no dataset.

    This tests the behavior when the thread integration has a preferred dataset.
    """
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.put(f"{url}/node/dataset/active", status=HTTPStatus.ACCEPTED)
    aioclient_mock.post(f"{url}/node/state", status=HTTPStatus.OK)

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

    assert aioclient_mock.mock_calls[-1][0] == "POST"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "enable"

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
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


async def test_hassio_discovery_flow_router_not_setup_has_preferred_2(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the hassio discovery flow when the border router has no dataset.

    This tests the behavior when the thread integration has a preferred dataset, but
    the preferred dataset is not using channel 15.
    """
    url = "http://core-silabs-multiprotocol:8081"
    aioclient_mock.get(f"{url}/node/dataset/active", status=HTTPStatus.NO_CONTENT)
    aioclient_mock.post(f"{url}/node/dataset/active", status=HTTPStatus.ACCEPTED)
    aioclient_mock.post(f"{url}/node/state", status=HTTPStatus.OK)

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
    assert aioclient_mock.mock_calls[-2][0] == "POST"
    assert aioclient_mock.mock_calls[-2][1].path == "/node/dataset/active"
    assert aioclient_mock.mock_calls[-2][2] == {
        "Channel": 15,
        "NetworkName": "home-assistant",
    }

    assert aioclient_mock.mock_calls[-1][0] == "POST"
    assert aioclient_mock.mock_calls[-1][1].path == "/node/state"
    assert aioclient_mock.mock_calls[-1][2] == "enable"

    expected_data = {
        "url": f"http://{HASSIO_DATA.config['host']}:{HASSIO_DATA.config['port']}",
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


@pytest.mark.parametrize("source", ("hassio", "user"))
async def test_config_flow_single_entry(hass: HomeAssistant, source: str) -> None:
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
            otbr.DOMAIN, context={"source": source}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    mock_setup_entry.assert_not_called()


async def test_options_flow_entry_not_setup(
    hass: HomeAssistant, otbr_config_entry: ConfigEntry
) -> None:
    """Test starting the options flow when the entry is not loaded."""
    await hass.config_entries.async_unload(otbr_config_entry.entry_id)
    result = await hass.config_entries.options.async_init(otbr_config_entry.entry_id)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "config_entry_not_setup"


async def test_options_flow_no_network_no_preferred_dataset(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=None,
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == ["create_network"]
    assert result["step_id"] == "thread_network_menu"


async def test_options_flow_err_network_no_preferred_dataset(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=None,
    ), patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", side_effect=HomeAssistantError
    ):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == ["create_network"]
    assert result["step_id"] == "thread_network_menu"


async def test_options_flow_same_preferred_dataset(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", status=HTTPStatus.NO_CONTENT)

    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=DATASET_CH16.hex(),
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH16):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == ["create_network"]
    assert result["step_id"] == "thread_network_menu"


@pytest.mark.parametrize(
    ("otbr_network", "menu_options"),
    [
        (
            None,
            ["create_network", "use_preferred_network"],
        ),
        (
            DATASET_CH15,
            ["create_network", "prefer_otbr_network", "use_preferred_network"],
        ),
    ],
)
async def test_options_flow_other_network(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
    otbr_network: bytes | None,
    menu_options: list[str],
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=DATASET_CH16.hex(),
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=otbr_network):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == menu_options
    assert result["step_id"] == "thread_network_menu"


async def test_options_flow_create_new_network(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=None,
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == ["create_network"]
    assert result["step_id"] == "thread_network_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "create_network"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "create_network"

    with patch(
        "homeassistant.components.otbr.config_flow.async_set_preferred_dataset",
    ) as set_preferred_mock, patch(
        "python_otbr_api.OTBR.set_enabled"
    ) as set_enabled_mock, patch(
        "python_otbr_api.OTBR.create_active_dataset"
    ) as create_active_dataset_mock, patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH15
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {}

    assert len(set_enabled_mock.mock_calls) == 2
    assert set_enabled_mock.mock_calls[0][1][0] is False
    assert set_enabled_mock.mock_calls[1][1][0] is True

    create_active_dataset_mock.assert_called_once_with(
        python_otbr_api.models.OperationalDataSet(
            channel=15, network_name="home-assistant"
        )
    )

    set_preferred_mock.assert_called_once()


async def test_options_flow_create_new_network_err(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=None,
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "create_network"},
    )
    with patch("python_otbr_api.OTBR.set_enabled", side_effect=HomeAssistantError):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_options_flow_create_new_network_empty(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=None,
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "create_network"},
    )

    with patch("python_otbr_api.OTBR.set_enabled"), patch(
        "python_otbr_api.OTBR.create_active_dataset"
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_options_flow_prefer_otbr_network(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=None,
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH15):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == ["create_network", "prefer_otbr_network"]
    assert result["step_id"] == "thread_network_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "prefer_otbr_network"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "prefer_otbr_network"

    with patch(
        "homeassistant.components.otbr.config_flow.async_set_preferred_dataset",
    ) as set_preferred_mock, patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH15
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {}

    set_preferred_mock.assert_called_once()


async def test_options_flow_prefer_otbr_network_err(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=None,
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH15):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "prefer_otbr_network"},
    )

    with patch(
        "python_otbr_api.OTBR.get_active_dataset_tlvs", side_effect=HomeAssistantError
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_options_flow_prefer_otbr_network_empty(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=None,
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=DATASET_CH15):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "prefer_otbr_network"},
    )

    with patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_options_flow_use_preferred_network(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=DATASET_CH15.hex(),
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == ["create_network", "use_preferred_network"]
    assert result["step_id"] == "thread_network_menu"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "use_preferred_network"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "use_preferred_network"

    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=DATASET_CH15.hex(),
    ) as get_preferred_mock, patch(
        "python_otbr_api.OTBR.set_enabled"
    ) as set_enabled_mock, patch(
        "python_otbr_api.OTBR.set_active_dataset_tlvs"
    ) as set_active_dataset_mock:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {}

    get_preferred_mock.assert_called_once()

    assert len(set_enabled_mock.mock_calls) == 2
    assert set_enabled_mock.mock_calls[0][1][0] is False
    assert set_enabled_mock.mock_calls[1][1][0] is True

    set_active_dataset_mock.assert_called_once_with(DATASET_CH15)


async def test_options_flow_use_preferred_network_no_preferred(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=DATASET_CH15.hex(),
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "use_preferred_network"},
    )

    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=None,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_options_flow_use_preferred_network_err(
    hass: HomeAssistant,
    otbr_config_entry: ConfigEntry,
) -> None:
    """Test the options flow."""
    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=DATASET_CH15.hex(),
    ), patch("python_otbr_api.OTBR.get_active_dataset_tlvs", return_value=None):
        result = await hass.config_entries.options.async_init(
            otbr_config_entry.entry_id
        )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "use_preferred_network"},
    )

    with patch(
        "homeassistant.components.otbr.config_flow.async_get_preferred_dataset",
        return_value=DATASET_CH15.hex(),
    ), patch("python_otbr_api.OTBR.set_enabled", side_effect=HomeAssistantError):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"
