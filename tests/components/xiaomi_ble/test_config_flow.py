"""Test the Xiaomi config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.xiaomi_ble.const import DOMAIN
from homeassistant.data_entry_flow import FlowResultType

from . import (
    LYWSDCGQ_SERVICE_INFO,
    MMC_T201_1_SERVICE_INFO,
    NOT_SENSOR_PUSH_SERVICE_INFO,
)

from tests.common import MockConfigEntry


async def test_async_step_bluetooth_valid_device(hass):
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MMC_T201_1_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "MMC_T201_1"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "00:81:F9:DD:6F:C1"


async def test_async_step_bluetooth_not_xiaomi(hass):
    """Test discovery via bluetooth not xiaomi."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=NOT_SENSOR_PUSH_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_async_step_user_no_devices_found(hass):
    """Test setup from service info cache with no devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_with_found_devices(hass):
    """Test setup from service info cache with devices found."""
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[LYWSDCGQ_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "58:2D:34:35:93:21"},
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "LYWSDCGQ"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "58:2D:34:35:93:21"


async def test_async_step_user_with_found_devices_already_setup(hass):
    """Test setup from service info cache with devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="58:2D:34:35:93:21",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[LYWSDCGQ_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_bluetooth_devices_already_setup(hass):
    """Test we can't start a flow if there is already a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:81:F9:DD:6F:C1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MMC_T201_1_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_already_in_progress(hass):
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MMC_T201_1_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MMC_T201_1_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
