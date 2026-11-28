"""Test the Laifen config flow."""

from unittest.mock import MagicMock

from laifen_ble import LaifenConnectionError, UnsupportedStateError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info

from homeassistant.components.laifen.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ADDRESS, LAIFEN_SERVICE_INFO, NAME, UNSUPPORTED_SERVICE_INFO


@pytest.mark.usefixtures("mock_setup_entry")
async def test_bluetooth_discovery(
    hass: HomeAssistant, mock_toothbrush: MagicMock
) -> None:
    """Test setting up a discovered toothbrush."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=LAIFEN_SERVICE_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    flow = hass.config_entries.flow.async_get(result["flow_id"])
    assert flow["context"]["title_placeholders"] == {"name": NAME}

    inject_bluetooth_service_info(hass, LAIFEN_SERVICE_INFO)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS
    mock_toothbrush.connect.assert_awaited_once()
    mock_toothbrush.disconnect.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_bluetooth_discovery_cannot_connect(
    hass: HomeAssistant, mock_toothbrush: MagicMock
) -> None:
    """Test recovering when the discovered toothbrush cannot be connected to."""
    connect = mock_toothbrush.connect.side_effect
    mock_toothbrush.connect.side_effect = LaifenConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=LAIFEN_SERVICE_INFO
    )
    inject_bluetooth_service_info(hass, LAIFEN_SERVICE_INFO)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_toothbrush.connect.side_effect = connect
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_bluetooth_discovery_toothbrush_gone(
    hass: HomeAssistant, mock_toothbrush: MagicMock
) -> None:
    """Test recovering when the discovered toothbrush is no longer seen."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=LAIFEN_SERVICE_INFO
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    mock_toothbrush.connect.assert_not_awaited()

    inject_bluetooth_service_info(hass, LAIFEN_SERVICE_INFO)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bluetooth_discovery_unsupported_firmware(
    hass: HomeAssistant, mock_toothbrush: MagicMock
) -> None:
    """Test discovering a toothbrush with a firmware that is not supported."""
    mock_toothbrush.connect.side_effect = UnsupportedStateError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=LAIFEN_SERVICE_INFO
    )
    inject_bluetooth_service_info(hass, LAIFEN_SERVICE_INFO)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_firmware"


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test discovering a toothbrush that is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=LAIFEN_SERVICE_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_already_in_progress(hass: HomeAssistant) -> None:
    """Test discovering a toothbrush that is already being set up."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=LAIFEN_SERVICE_INFO
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=LAIFEN_SERVICE_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.usefixtures("mock_setup_entry", "mock_toothbrush")
async def test_user(hass: HomeAssistant) -> None:
    """Test picking a discovered toothbrush."""
    inject_bluetooth_service_info(hass, LAIFEN_SERVICE_INFO)
    inject_bluetooth_service_info(hass, UNSUPPORTED_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_cannot_connect(
    hass: HomeAssistant, mock_toothbrush: MagicMock
) -> None:
    """Test recovering when the picked toothbrush cannot be connected to."""
    inject_bluetooth_service_info(hass, LAIFEN_SERVICE_INFO)
    connect = mock_toothbrush.connect.side_effect
    mock_toothbrush.connect.side_effect = LaifenConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_toothbrush.connect.side_effect = connect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_unsupported_firmware(
    hass: HomeAssistant, mock_toothbrush: MagicMock
) -> None:
    """Test picking a toothbrush with a firmware that is not supported."""
    inject_bluetooth_service_info(hass, LAIFEN_SERVICE_INFO)
    mock_toothbrush.connect.side_effect = UnsupportedStateError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_firmware"


async def test_user_no_devices(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that configured and unsupported toothbrushes are not offered."""
    mock_config_entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, LAIFEN_SERVICE_INFO)
    inject_bluetooth_service_info(hass, UNSUPPORTED_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test picking a toothbrush that got configured meanwhile."""
    inject_bluetooth_service_info(hass, LAIFEN_SERVICE_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
