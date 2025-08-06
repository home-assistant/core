"""Test the ToGrill config flow."""

from unittest.mock import Mock

from bleak.exc import BleakError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.togrill.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TOGRILL_SERVICE_INFO, TOGRILL_SERVICE_INFO_NO_NAME

from tests.components.bluetooth import inject_bluetooth_service_info

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_selection(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test we can select a device."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)
    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO_NO_NAME)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "00000000-0000-0000-0000-000000000001"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "address": "00000000-0000-0000-0000-000000000001",
        "model": "Pro-05",
        "probe_count": 0,
    }
    assert result["title"] == "Pro-05"
    assert result["result"].unique_id == "00000000-0000-0000-0000-000000000001"


async def test_failed_connect(
    hass: HomeAssistant,
    mock_client: Mock,
    mock_client_class: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test we can select a device."""

    mock_client_class.connect.side_effect = BleakError("Failed to connect")

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "00000000-0000-0000-0000-000000000001"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "failed_to_read_config"


async def test_failed_read(
    hass: HomeAssistant,
    mock_client: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test we can select a device."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_client.read.side_effect = BleakError("something went wrong")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "00000000-0000-0000-0000-000000000001"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "failed_to_read_config"


async def test_no_devices(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test missing device."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO_NO_NAME)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_bluetooth(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test bluetooth device discovery."""

    # Inject the service info will trigger the flow to start
    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = next(iter(hass.config_entries.flow.async_progress_by_handler(DOMAIN)))

    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "address": "00000000-0000-0000-0000-000000000001",
        "model": "Pro-05",
        "probe_count": 0,
    }
    assert result["title"] == "Pro-05"
    assert result["result"].unique_id == "00000000-0000-0000-0000-000000000001"
