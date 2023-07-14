"""Test the SensorPush config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.sensorpush.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import HTPWX_SERVICE_INFO, HTW_SERVICE_INFO, NOT_SENSOR_PUSH_SERVICE_INFO

from tests.common import MockConfigEntry


async def test_async_step_bluetooth_valid_device(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HTPWX_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    with patch(
        "homeassistant.components.sensorpush.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "HTP.xw F4D"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "4125DDBA-2774-4851-9889-6AADDD4CAC3D"


async def test_async_step_bluetooth_not_sensorpush(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth not sensorpush."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=NOT_SENSOR_PUSH_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_async_step_user_no_devices_found(hass: HomeAssistant) -> None:
    """Test setup from service info cache with no devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_with_found_devices(hass: HomeAssistant) -> None:
    """Test setup from service info cache with devices found."""
    with patch(
        "homeassistant.components.sensorpush.config_flow.async_discovered_service_info",
        return_value=[HTW_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    with patch(
        "homeassistant.components.sensorpush.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "61DE521B-F0BF-9F44-64D4-75BBE1738105"},
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "HT.w 0CA1"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "61DE521B-F0BF-9F44-64D4-75BBE1738105"


async def test_async_step_user_device_added_between_steps(hass: HomeAssistant) -> None:
    """Test the device gets added via another flow between steps."""
    with patch(
        "homeassistant.components.sensorpush.config_flow.async_discovered_service_info",
        return_value=[HTW_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sensorpush.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "61DE521B-F0BF-9F44-64D4-75BBE1738105"},
        )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_async_step_user_with_found_devices_already_setup(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sensorpush.config_flow.async_discovered_service_info",
        return_value=[HTW_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_bluetooth_devices_already_setup(hass: HomeAssistant) -> None:
    """Test we can't start a flow if there is already a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HTW_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_already_in_progress(hass: HomeAssistant) -> None:
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HTW_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HTW_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_async_step_user_takes_precedence_over_discovery(
    hass: HomeAssistant,
) -> None:
    """Test manual setup takes precedence over discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=HTW_SERVICE_INFO,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "homeassistant.components.sensorpush.config_flow.async_discovered_service_info",
        return_value=[HTW_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.sensorpush.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "61DE521B-F0BF-9F44-64D4-75BBE1738105"},
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "HT.w 0CA1"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "61DE521B-F0BF-9F44-64D4-75BBE1738105"

    # Verify the original one was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)
