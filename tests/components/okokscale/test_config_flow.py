"""Tests for the OKOK Scale config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.okokscale.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_IGNORE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    NOT_OKOK_SERVICE_INFO,
    OKOK_20_SERVICE_INFO,
    OKOK_20_TITLE,
    OKOK_C0_SERVICE_INFO,
    OKOK_C0_TITLE,
    OKOK_F0_ADDRESS,
    OKOK_F0_SERVICE_INFO,
    OKOK_F0_TITLE,
)

from tests.common import MockConfigEntry

DISCOVERY = (
    "homeassistant.components.okokscale.config_flow.async_discovered_service_info"
)


@pytest.mark.parametrize(
    ("service_info", "title"),
    [
        (OKOK_F0_SERVICE_INFO, OKOK_F0_TITLE),
        (OKOK_20_SERVICE_INFO, OKOK_20_TITLE),
        (OKOK_C0_SERVICE_INFO, OKOK_C0_TITLE),
    ],
)
async def test_async_step_bluetooth_valid_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    service_info: BluetoothServiceInfo,
    title: str,
) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["data"] == {}
    assert result["result"].unique_id == service_info.address


async def test_async_step_bluetooth_not_supported(hass: HomeAssistant) -> None:
    """Test bluetooth discovery rejects advertisements that are not supported."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=NOT_OKOK_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_async_step_user_no_devices_found(hass: HomeAssistant) -> None:
    """Test setup from service info cache with no devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_with_found_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setup from service info cache with devices found."""
    with patch(DISCOVERY, return_value=[OKOK_F0_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": OKOK_F0_ADDRESS},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == OKOK_F0_TITLE
    assert result["data"] == {}
    assert result["result"].unique_id == OKOK_F0_ADDRESS


async def async_step_user_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the user step aborts when the discovered device is already configured."""
    mock_config_entry.add_to_hass(hass)
    with patch(DISCOVERY, return_value=[OKOK_F0_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_bluetooth_devices_already_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we can't start a flow if there is already a config entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=OKOK_F0_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_already_in_progress(hass: HomeAssistant) -> None:
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=OKOK_F0_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=OKOK_F0_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_async_step_user_device_added_between_steps(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the device gets added via another flow between steps."""
    with patch(DISCOVERY, return_value=[OKOK_F0_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": OKOK_F0_ADDRESS},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_user_replace_ignored(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setup from service info can replace an ignored entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=OKOK_F0_ADDRESS,
        source=SOURCE_IGNORE,
        data={},
    )
    entry.add_to_hass(hass)
    with patch(DISCOVERY, return_value=[OKOK_F0_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": OKOK_F0_ADDRESS},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == OKOK_F0_TITLE
    assert result["result"].unique_id == OKOK_F0_ADDRESS


async def test_async_step_user_takes_precedence_over_discovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual setup takes precedence over discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=OKOK_F0_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(DISCOVERY, return_value=[OKOK_F0_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": OKOK_F0_ADDRESS},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == OKOK_F0_TITLE
    assert result["result"].unique_id == OKOK_F0_ADDRESS

    # Verify the original discovery flow was aborted.
    assert not hass.config_entries.flow.async_progress(DOMAIN)
