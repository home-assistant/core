"""Tests for the Marstek config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.marstek.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import SelectSelector

from . import (
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

DISCOVERED_DEVICE = {
    "id": 0,
    "device_type": TEST_DEVICE_TYPE,
    "version": TEST_VERSION,
    "wifi_name": TEST_WIFI_NAME,
    "ip": TEST_HOST,
    "wifi_mac": TEST_WIFI_MAC,
    "ble_mac": TEST_BLE_MAC,
    "mac": TEST_MAC,
}

DISCOVERED_DEVICE_2 = {
    **DISCOVERED_DEVICE,
    "ip": "192.168.1.101",
    "wifi_name": "",
    "mac": "AA:BB:CC:DD:EE:00",
    "wifi_mac": "AA:BB:CC:DD:EE:00",
}

EXPECTED_ENTRY_DATA = {
    CONF_HOST: TEST_HOST,
    CONF_MAC: TEST_MAC,
    "device_type": TEST_DEVICE_TYPE,
    "version": TEST_VERSION,
    "wifi_name": TEST_WIFI_NAME,
    "wifi_mac": TEST_WIFI_MAC,
    "ble_mac": TEST_BLE_MAC,
}

EXPECTED_TITLE = f"Marstek {TEST_DEVICE_TYPE} v{TEST_VERSION} ({TEST_HOST})"
EXPECTED_DEVICE_OPTION = (
    f"{TEST_DEVICE_TYPE} v{TEST_VERSION} ({TEST_WIFI_NAME}) - {TEST_HOST}"
)
EXPECTED_DEVICE_OPTION_2 = (
    f"{TEST_DEVICE_TYPE} v{TEST_VERSION} (No WiFi) - 192.168.1.101"
)


async def test_user_step_shows_menu(hass: HomeAssistant) -> None:
    """Test the user step exposes discovery and manual setup choices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == {
        "discover": "Search for devices on the local network",
        "manual": "Enter device IP address",
    }


async def test_discovery_flow_creates_entry(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test adding a device discovered on the local network."""
    mock_udp_client.discover_devices.return_value = [DISCOVERED_DEVICE]

    with patch(
        "homeassistant.components.marstek.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "discover"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": EXPECTED_DEVICE_OPTION}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EXPECTED_TITLE
    assert result["data"] == EXPECTED_ENTRY_DATA
    assert result["result"].unique_id == TEST_MAC
    mock_setup_entry.assert_called_once()


async def test_discovery_flow_shows_device_labels(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test discovered device selector options have visible labels."""
    mock_udp_client.discover_devices.return_value = [
        DISCOVERED_DEVICE,
        DISCOVERED_DEVICE_2,
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    await hass.async_block_till_done()

    selector = next(iter(result["data_schema"].schema.values()))

    assert isinstance(selector, SelectSelector)
    assert selector.config["options"] == [
        {"value": EXPECTED_DEVICE_OPTION, "label": EXPECTED_DEVICE_OPTION},
        {"value": EXPECTED_DEVICE_OPTION_2, "label": EXPECTED_DEVICE_OPTION_2},
    ]


async def test_manual_flow_creates_entry(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test adding a device by IP address."""
    mock_udp_client.get_device_info.return_value = MOCK_DISCOVERY_RESPONSE["result"]

    with patch(
        "homeassistant.components.marstek.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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
    mock_udp_client.get_device_info.assert_awaited_once()
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


async def test_discover_no_devices(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test discovery shows an error when no devices are found."""
    mock_udp_client.discover_devices.return_value = []

    with patch(
        "homeassistant.components.marstek.config_flow.asyncio.sleep",
        new=AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    assert result["errors"] == {"base": "no_devices_found"}


async def test_discover_failed(hass: HomeAssistant, mock_udp_client: MagicMock) -> None:
    """Test discovery shows an error when the broadcast fails."""
    mock_udp_client.discover_devices.side_effect = OSError("network down")

    with patch(
        "homeassistant.components.marstek.config_flow.asyncio.sleep",
        new=AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    assert result["errors"] == {"base": "discovery_failed"}


async def test_discover_retry_succeeds(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test discovery succeeds on the retry attempt."""
    mock_udp_client.discover_devices.side_effect = [[], [DISCOVERED_DEVICE]]

    with patch(
        "homeassistant.components.marstek.config_flow.asyncio.sleep",
        new=AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    selector = next(iter(result["data_schema"].schema.values()))
    assert selector.config["options"] == [
        {"value": EXPECTED_DEVICE_OPTION, "label": EXPECTED_DEVICE_OPTION},
    ]


async def test_discover_failed_uses_cache(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test discovery falls back to cached devices when the broadcast fails."""
    mock_udp_client.discover_devices.side_effect = OSError("network down")
    mock_udp_client.get_discovery_cache.return_value = [DISCOVERED_DEVICE]

    with patch(
        "homeassistant.components.marstek.config_flow.asyncio.sleep",
        new=AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    selector = next(iter(result["data_schema"].schema.values()))
    assert selector.config["options"] == [
        {"value": EXPECTED_DEVICE_OPTION, "label": EXPECTED_DEVICE_OPTION},
    ]


async def test_discovery_duplicate_device_names(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test duplicate device names are deduplicated in the selector."""
    mock_udp_client.discover_devices.return_value = [
        DISCOVERED_DEVICE,
        DISCOVERED_DEVICE,
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    await hass.async_block_till_done()

    selector = next(iter(result["data_schema"].schema.values()))
    assert selector.config["options"] == [
        {"value": EXPECTED_DEVICE_OPTION, "label": EXPECTED_DEVICE_OPTION},
        {
            "value": f"{EXPECTED_DEVICE_OPTION} #2",
            "label": f"{EXPECTED_DEVICE_OPTION} #2",
        },
    ]


async def test_manual_cannot_connect(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test manual setup shows an error when the device times out."""
    mock_udp_client.get_device_info.side_effect = TimeoutError("timeout")

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
    assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_device_not_found(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test manual setup shows an error when the device is unreachable."""
    mock_udp_client.get_device_info.side_effect = OSError("no route to host")

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
    assert result["errors"] == {"base": "device_not_found"}


async def test_manual_invalid_device_data(
    hass: HomeAssistant, mock_udp_client: MagicMock
) -> None:
    """Test manual setup errors when the device returns invalid data."""
    mock_udp_client.get_device_info.side_effect = None
    mock_udp_client.get_device_info.return_value = None

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
    assert result["errors"] == {"base": "device_not_found"}
