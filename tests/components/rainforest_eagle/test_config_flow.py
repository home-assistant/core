"""Test the Rainforest Eagle config flow."""

from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.rainforest_eagle.const import (
    CONF_CLOUD_ID,
    CONF_HARDWARE_ADDRESS,
    CONF_INSTALL_CODE,
    DOMAIN,
    TYPE_EAGLE_200,
)
from homeassistant.components.rainforest_eagle.data import CannotConnect, InvalidAuth
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form_one_meter(hass: HomeAssistant) -> None:
    """Test flow auto-selects the meter and sets up the entry if only one meter is present, regardless of its connection status."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    mock_meter = MagicMock()
    mock_meter.hardware_address = "mock-hw"
    mock_meter.connection_status = "Connected"

    with (
        patch(
            "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
            return_value=(TYPE_EAGLE_200, [mock_meter]),
        ),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result_2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )
        await hass.async_block_till_done()

    assert result_2["type"] is FlowResultType.CREATE_ENTRY
    assert result_2["title"] == "abcdef"
    assert result_2["data"] == {
        CONF_TYPE: TYPE_EAGLE_200,
        CONF_HOST: "192.168.1.55",
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "123456",
        CONF_HARDWARE_ADDRESS: "mock-hw",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # Repeat the test with the only meter being not connected
    result_3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result_3["type"] is FlowResultType.FORM
    assert result_3["errors"] is None

    mock_meter_1 = MagicMock()
    mock_meter_1.hardware_address = "mock-hw"
    mock_meter_1.connection_status = "Not Joined"

    with (
        patch(
            "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
            return_value=(TYPE_EAGLE_200, [mock_meter_1]),
        ),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result_4 = await hass.config_entries.flow.async_configure(
            result_3["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )
        await hass.async_block_till_done()

    assert result_4["type"] is FlowResultType.CREATE_ENTRY
    assert result_4["title"] == "abcdef"
    assert result_4["data"] == {
        CONF_TYPE: TYPE_EAGLE_200,
        CONF_HOST: "192.168.1.55",
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "123456",
        CONF_HARDWARE_ADDRESS: "mock-hw",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_multiple_meters_first_connected(hass: HomeAssistant) -> None:
    """Test flow auto-selects the first connected meter if present among multiple meters."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # Create mock meter objects
    mock_meter_1 = MagicMock()
    mock_meter_1.hardware_address = "meter-1"
    mock_meter_1.connection_status = "Not Joined"

    mock_meter_2 = MagicMock()
    mock_meter_2.hardware_address = "meter-2"
    mock_meter_2.connection_status = "Not Joined"

    mock_meter_3 = MagicMock()
    mock_meter_3.hardware_address = "meter-3"
    mock_meter_3.connection_status = "Connected"

    with (
        patch(
            "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
            return_value=(TYPE_EAGLE_200, [mock_meter_1, mock_meter_2, mock_meter_3]),
        ),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )
        await hass.async_block_till_done()

    # Should create the entry immediately with the first connected meter
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "abcdef"
    assert result2["data"] == {
        CONF_TYPE: TYPE_EAGLE_200,
        CONF_HOST: "192.168.1.55",
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "123456",
        CONF_HARDWARE_ADDRESS: "meter-3",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_multiple_meters_none_connected(hass: HomeAssistant) -> None:
    """Test meter selection when multiple meters are returned and none are connected."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # Create mock meter objects
    mock_meter_1 = MagicMock()
    mock_meter_1.hardware_address = "meter-1"
    mock_meter_1.connection_status = "Not Joined"

    mock_meter_2 = MagicMock()
    mock_meter_2.hardware_address = "meter-2"
    mock_meter_2.connection_status = "Not Joined"

    with (
        patch(
            "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
            return_value=(TYPE_EAGLE_200, [mock_meter_1, mock_meter_2]),
        ),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )
        await hass.async_block_till_done()

    # Should not have create the entities, yet
    assert len(mock_setup_entry.mock_calls) == 0

    # Should show meter selection form
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "meter_select"

    # Now select a meter
    with (
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry_2,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_HARDWARE_ADDRESS: "meter-2"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "abcdef"
    assert result3["data"] == {
        CONF_TYPE: TYPE_EAGLE_200,
        CONF_HOST: "192.168.1.55",
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "123456",
        CONF_HARDWARE_ADDRESS: "meter-2",
    }
    assert len(mock_setup_entry_2.mock_calls) == 1


async def test_form_no_meters(hass: HomeAssistant) -> None:
    """Test proper flow with no meters."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
            return_value=(TYPE_EAGLE_200, []),
        ),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "abcdef"
    assert result2["data"] == {
        CONF_TYPE: TYPE_EAGLE_200,
        CONF_HOST: "192.168.1.55",
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "123456",
        CONF_HARDWARE_ADDRESS: None,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aioeagle.EagleHub.get_device_list",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aioeagle.EagleHub.get_device_list",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
