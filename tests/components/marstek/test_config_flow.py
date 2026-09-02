"""Tests for the Marstek config flow."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.marstek.const import (
    CONF_BLE_MAC,
    CONF_DEVICE_TYPE,
    CONF_VERSION,
    CONF_WIFI_MAC,
    CONF_WIFI_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCK_DISCOVERY_RESPONSE,
    TEST_BLE_MAC,
    TEST_DEVICE_TYPE,
    TEST_HOST,
    TEST_MAC,
    TEST_VERSION,
    TEST_WIFI_MAC,
    TEST_WIFI_NAME,
)

from tests.common import MockConfigEntry


def _data_schema(result: config_entries.ConfigFlowResult) -> vol.Schema:
    """Return the data schema from a flow result."""
    data_schema = result["data_schema"]
    assert data_schema is not None
    return data_schema


DISCOVERED_DEVICE = MOCK_DISCOVERY_RESPONSE["result"]

DISCOVERED_DEVICE_DUPLICATE_NAME = replace(
    DISCOVERED_DEVICE,
    mac="AA:BB:CC:DD:EE:00",
    wifi_mac="AA:BB:CC:DD:EE:00",
)

DISCOVERED_DEVICE_WITHOUT_STABLE_ID = replace(
    DISCOVERED_DEVICE, mac="", wifi_mac="", ble_mac=""
)

UNSUPPORTED_DEVICE_INFO = replace(DISCOVERED_DEVICE, device_type="VenusE 2.0")

UNSUPPORTED_DISCOVERED_DEVICE = UNSUPPORTED_DEVICE_INFO

EXPECTED_ENTRY_DATA = {
    CONF_HOST: TEST_HOST,
    CONF_MAC: TEST_MAC,
    CONF_DEVICE_TYPE: TEST_DEVICE_TYPE,
    CONF_VERSION: TEST_VERSION,
    CONF_WIFI_NAME: TEST_WIFI_NAME,
    CONF_WIFI_MAC: TEST_WIFI_MAC,
    CONF_BLE_MAC: TEST_BLE_MAC,
}

EXPECTED_TITLE = f"Marstek {TEST_DEVICE_TYPE} v{TEST_VERSION} ({TEST_HOST})"
EXPECTED_DEVICE_OPTION = (
    f"{TEST_DEVICE_TYPE} v{TEST_VERSION} ({TEST_WIFI_NAME}) - {TEST_HOST}"
)


async def test_discovery_flow_creates_entry(
    hass: HomeAssistant, mock_udp_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test adding a device discovered on the local network."""
    mock_udp_client.discover_devices.return_value = [DISCOVERED_DEVICE]
    mock_udp_client.get_device_info.return_value = MOCK_DISCOVERY_RESPONSE["result"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: "0"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EXPECTED_TITLE
    assert result["data"] == EXPECTED_ENTRY_DATA
    assert result["result"].unique_id == TEST_MAC
    mock_udp_client.get_device_info.assert_awaited_once_with(TEST_HOST)
    mock_setup_entry.assert_called_once()


async def test_discovery_flow_duplicate_device_names(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test duplicate device names are deduplicated in the selector."""
    mock_udp_client.discover_devices.return_value = [
        DISCOVERED_DEVICE,
        DISCOVERED_DEVICE_DUPLICATE_NAME,
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    await hass.async_block_till_done()

    selector = next(iter(_data_schema(result).schema.values()))

    assert selector.config["options"] == [
        {"value": "0", "label": EXPECTED_DEVICE_OPTION},
        {"value": "1", "label": f"{EXPECTED_DEVICE_OPTION} #2"},
    ]


async def test_discovery_flow_filters_unsupported_devices(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test discovery only shows supported device types."""
    mock_udp_client.discover_devices.return_value = [
        UNSUPPORTED_DISCOVERED_DEVICE,
        DISCOVERED_DEVICE,
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    await hass.async_block_till_done()

    selector = next(iter(_data_schema(result).schema.values()))

    assert selector.config["options"] == [
        {"value": "0", "label": EXPECTED_DEVICE_OPTION},
    ]


async def test_discovery_flow_errors_if_only_unsupported_devices_found(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test discovery shows an error when only unsupported devices are found."""
    mock_udp_client.discover_devices.return_value = [UNSUPPORTED_DISCOVERED_DEVICE]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    assert result["errors"] == {"base": "unsupported_device"}


async def test_discovery_flow_aborts_if_selected_device_is_unsupported(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test discovery aborts if the selected device is no longer supported."""
    mock_udp_client.discover_devices.return_value = [DISCOVERED_DEVICE]
    mock_udp_client.get_device_info.return_value = UNSUPPORTED_DEVICE_INFO

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: "0"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_device"


async def test_discovery_flow_aborts_without_stable_unique_id(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test discovered devices without a stable unique ID are not configured."""
    mock_udp_client.discover_devices.return_value = [
        DISCOVERED_DEVICE_WITHOUT_STABLE_ID
    ]
    mock_udp_client.get_device_info.side_effect = None
    mock_udp_client.get_device_info.return_value = DISCOVERED_DEVICE_WITHOUT_STABLE_ID

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: "0"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_unique_id"


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        pytest.param(TimeoutError("timeout"), "cannot_connect", id="timeout"),
        pytest.param(TypeError("bad data"), "device_not_found", id="typeerror"),
    ],
)
async def test_discovery_flow_select_device_errors(
    hass: HomeAssistant,
    mock_udp_client: MagicMock,
    error: Exception,
    expected_reason: str,
) -> None:
    """Test errors when selecting a discovered device."""
    mock_udp_client.discover_devices.return_value = [DISCOVERED_DEVICE]
    mock_udp_client.get_device_info.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: "0"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    assert result["errors"] == {"base": expected_reason}


async def test_manual_flow_creates_entry(
    hass: HomeAssistant, mock_udp_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test adding a device by IP address."""
    mock_udp_client.get_device_info.return_value = MOCK_DISCOVERY_RESPONSE["result"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EXPECTED_TITLE
    assert result["data"] == EXPECTED_ENTRY_DATA
    assert result["result"].unique_id == TEST_MAC
    mock_udp_client.get_device_info.assert_awaited_once_with(TEST_HOST)
    mock_setup_entry.assert_called_once()


async def test_manual_flow_aborts_if_host_configured(hass: HomeAssistant) -> None:
    """Test manual setup aborts when the host is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=EXPECTED_TITLE,
        data=EXPECTED_ENTRY_DATA,
        unique_id=TEST_HOST,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_flow_errors_if_device_type_is_unsupported(
    hass: HomeAssistant,
    mock_udp_client: MagicMock,
) -> None:
    """Test manual setup errors when the device type is unsupported."""
    mock_udp_client.get_device_info.return_value = UNSUPPORTED_DEVICE_INFO

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "unsupported_device"}


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        pytest.param(TimeoutError("timeout"), "cannot_connect", id="timeout"),
        pytest.param(OSError("no route"), "cannot_connect", id="oserror"),
        pytest.param(TypeError("bad data"), "device_not_found", id="typeerror"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_flow_errors_are_recoverable(
    hass: HomeAssistant,
    mock_udp_client: MagicMock,
    error: Exception,
    expected_reason: str,
) -> None:
    """Test manual setup errors can be retried successfully."""
    mock_udp_client.get_device_info.side_effect = [
        error,
        MOCK_DISCOVERY_RESPONSE["result"],
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": expected_reason}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_MAC


async def test_discover_no_devices(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test discovery shows an error when no devices are found."""
    mock_udp_client.discover_devices.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    assert result["errors"] == {"base": "no_devices_found"}


async def test_discovery_empty_error_form_rediscovers(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test submitting an empty discovery error form retries discovery."""
    mock_udp_client.discover_devices.side_effect = [[], [DISCOVERED_DEVICE]]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices_found"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    selector = next(iter(_data_schema(result).schema.values()))
    assert selector.config["options"] == [
        {"value": "0", "label": EXPECTED_DEVICE_OPTION},
    ]


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        pytest.param(OSError("network down"), "discovery_failed", id="oserror"),
        pytest.param(TypeError("bad data"), "discovery_failed", id="typeerror"),
        pytest.param(TimeoutError("timeout"), "discovery_failed", id="timeout"),
    ],
)
async def test_discovery_flow_errors_are_recoverable(
    hass: HomeAssistant,
    mock_udp_client: MagicMock,
    error: Exception,
    expected_reason: str,
) -> None:
    """Test discovery errors can be retried successfully."""
    mock_udp_client.discover_devices.side_effect = [error, [DISCOVERED_DEVICE]]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    assert result["errors"] == {"base": expected_reason}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    selector = next(iter(_data_schema(result).schema.values()))
    assert selector.config["options"] == [
        {"value": "0", "label": EXPECTED_DEVICE_OPTION},
    ]


async def test_discover_failed_when_client_setup_fails(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test discovery shows an error when the UDP client cannot be created."""
    with (
        patch(
            "homeassistant.components.marstek.config_flow.async_create_udp_client",
            side_effect=[OSError("network down"), mock_udp_client],
        ),
    ):
        mock_udp_client.discover_devices.return_value = [DISCOVERED_DEVICE]

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "discover"
        assert result["errors"] == {"base": "discovery_failed"}

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    selector = next(iter(_data_schema(result).schema.values()))
    assert selector.config["options"] == [
        {"value": "0", "label": EXPECTED_DEVICE_OPTION},
    ]
