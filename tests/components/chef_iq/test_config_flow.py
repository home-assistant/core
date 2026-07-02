"""Test the Chef iQ config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.chef_iq.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_IGNORE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    ADDRESS,
    CHEFIQ_TEMPERATURE_SERVICE_INFO,
    CHEFIQ_UNSUPPORTED_SERVICE_INFO,
    IQ_SENSE_SERVICE_INFO,
    NOT_CHEFIQ_SERVICE_INFO,
    TITLE,
)

from tests.common import MockConfigEntry

DISCOVERY = "homeassistant.components.chef_iq.config_flow.async_discovered_service_info"


async def test_async_step_bluetooth_valid_device(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=CHEFIQ_TEMPERATURE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {}
    assert result["result"].unique_id == ADDRESS


@pytest.mark.parametrize(
    "service_info",
    [
        NOT_CHEFIQ_SERVICE_INFO,
        IQ_SENSE_SERVICE_INFO,
        CHEFIQ_UNSUPPORTED_SERVICE_INFO,
    ],
)
async def test_async_step_bluetooth_not_supported(
    hass: HomeAssistant, service_info: BluetoothServiceInfo
) -> None:
    """Test bluetooth discovery rejects advertisements that are not a probe."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=service_info,
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
    with patch(DISCOVERY, return_value=[CHEFIQ_TEMPERATURE_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": ADDRESS},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {}
    assert result["result"].unique_id == ADDRESS


@pytest.mark.parametrize(
    ("discovered", "existing_entry"),
    [
        ([IQ_SENSE_SERVICE_INFO], False),
        ([CHEFIQ_TEMPERATURE_SERVICE_INFO], True),
    ],
)
async def test_async_step_user_no_eligible_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    discovered: list[BluetoothServiceInfo],
    existing_entry: bool,
) -> None:
    """Test the user step aborts when no eligible device can be offered.

    Either the only discovered device is the unsupported iQ Sense hub, or the
    discovered probe is already configured.
    """
    if existing_entry:
        mock_config_entry.add_to_hass(hass)
    with patch(DISCOVERY, return_value=discovered):
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
        data=CHEFIQ_TEMPERATURE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_already_in_progress(hass: HomeAssistant) -> None:
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=CHEFIQ_TEMPERATURE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=CHEFIQ_TEMPERATURE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_async_step_user_device_added_between_steps(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the device gets added via another flow between steps."""
    with patch(DISCOVERY, return_value=[CHEFIQ_TEMPERATURE_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": ADDRESS},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_user_replace_ignored(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setup from service info can replace an ignored entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        source=SOURCE_IGNORE,
        data={},
    )
    entry.add_to_hass(hass)
    with patch(DISCOVERY, return_value=[CHEFIQ_TEMPERATURE_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": ADDRESS},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["result"].unique_id == ADDRESS


async def test_async_step_user_takes_precedence_over_discovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual setup takes precedence over discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=CHEFIQ_TEMPERATURE_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(DISCOVERY, return_value=[CHEFIQ_TEMPERATURE_SERVICE_INFO]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": ADDRESS},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["result"].unique_id == ADDRESS

    # Verify the original discovery flow was aborted.
    assert not hass.config_entries.flow.async_progress(DOMAIN)
