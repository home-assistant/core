"""Test the Rainforest Eagle config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.rainforest_eagle.const import (
    CONF_CLOUD_ID,
    CONF_HARDWARE_ADDRESS,
    CONF_INSTALL_CODE,
    DOMAIN,
    TYPE_EAGLE_100,
    TYPE_EAGLE_200,
)
from homeassistant.components.rainforest_eagle.data import CannotConnect, InvalidAuth
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _mock_reconfigure_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a mock config entry for reconfigure tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="abcdef",
        unique_id="abcdef",
        data={
            CONF_TYPE: TYPE_EAGLE_200,
            CONF_HOST: "192.168.1.55",
            CONF_CLOUD_ID: "abcdef",
            CONF_INSTALL_CODE: "123456",
            CONF_HARDWARE_ADDRESS: "meter-1",
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_form_multiple_meters_first_connected(hass: HomeAssistant) -> None:
    """Test EAGLE-200 flow with multiple meters, one connected."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # Simulate multiple meters with one connected
    class MockElectricMeter:
        def __init__(self, hardware_address, connection_status) -> None:
            self.hardware_address = hardware_address
            self.connection_status = connection_status

    meters = [
        MockElectricMeter("meter-1", "Not Joined"),
        MockElectricMeter("meter-2", "Connected"),
        MockElectricMeter("meter-3", "Not Joined"),
    ]

    with (
        patch(
            "aioeagle.EagleHub.get_device_list",
            return_value=meters,
        ),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "abcdef"
    assert result["data"] == {
        CONF_TYPE: TYPE_EAGLE_200,
        CONF_HOST: "192.168.1.55",
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "123456",
        CONF_HARDWARE_ADDRESS: "meter-2",
    }
    assert result["result"].unique_id == "abcdef"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_eagle_200_meters_none_connected(hass: HomeAssistant) -> None:
    """Test EAGLE-200 flow with all meters disconnected."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # Simulate all meters being disconnected
    class MockElectricMeter:
        def __init__(self, hardware_address, connection_status) -> None:
            self.hardware_address = hardware_address
            self.connection_status = connection_status

    meters = [
        MockElectricMeter("meter-1", "Not Joined"),
        MockElectricMeter("meter-2", "Not Joined"),
        MockElectricMeter("meter-3", "Not Joined"),
    ]

    with patch(
        "aioeagle.EagleHub.get_device_list",
        return_value=meters,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_meters_connected"}


async def test_form_eagle_200_no_meters(hass: HomeAssistant) -> None:
    """Test EAGLE-200 flow with an empty list of meters."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # Simulate no meters (empty list)
    with (
        patch(
            "aioeagle.EagleHub.get_device_list",
            return_value=[],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_meters_connected"}


async def test_form_eagle_100(hass: HomeAssistant) -> None:
    """Test EAGLE-100 flow with legacy response."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # Patch get_device_list to raise KeyError (expected from
    # EAGLE-100), and async_add_executor_job to return proper
    # EAGLE-100 response
    eagle_100_response = {"NetworkInfo": {"ModelId": "Z109-EAGLE"}}

    with (
        patch(
            "aioeagle.EagleHub.get_device_list",
            side_effect=KeyError,
        ),
        patch(
            "eagle100.Eagle.get_network_info",
            return_value=eagle_100_response,
        ),
        patch(
            "homeassistant.core.HomeAssistant.async_add_executor_job",
            return_value=eagle_100_response,
        ),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "abcdef"
    assert result["data"] == {
        CONF_TYPE: TYPE_EAGLE_100,
        CONF_HOST: "192.168.1.55",
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "123456",
        CONF_HARDWARE_ADDRESS: None,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_unknown_device_type(hass: HomeAssistant) -> None:
    """Test flow when device type cannot be determined."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    # Patch get_device_list to raise KeyError (expected from
    # EAGLE-100), and async_add_executor_job to return an unknown
    # device response
    unknown_device_response = {"NetworkInfo": {"ModelId": "UNKNOWN-DEVICE"}}

    with (
        patch(
            "aioeagle.EagleHub.get_device_list",
            side_effect=KeyError,
        ),
        patch(
            "eagle100.Eagle.get_network_info",
            return_value=unknown_device_response,
        ),
        patch(
            "homeassistant.core.HomeAssistant.async_add_executor_job",
            return_value=unknown_device_response,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown_device_type"}


async def test_form_unsupported_device_type(hass: HomeAssistant) -> None:
    """Test flow when device type is unsupported."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
        return_value=("UNSUPPORTED_DEVICE_TYPE", None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_device_type"}


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test flow when an unexpected exception occurs."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aioeagle.EagleHub.get_device_list",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aioeagle.EagleHub.get_device_list",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_form(hass: HomeAssistant) -> None:
    """Test reconfigure shows the form."""
    entry = _mock_reconfigure_entry(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}


async def test_reconfigure_eagle_200(hass: HomeAssistant) -> None:
    """Test reconfigure updates an EAGLE-200 entry."""
    entry = _mock_reconfigure_entry(hass)
    result = await entry.start_reconfigure_flow(hass)

    with (
        patch(
            "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
            return_value=(TYPE_EAGLE_200, "meter-2"),
        ),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "654321",
                CONF_HOST: "192.168.1.56",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_TYPE: TYPE_EAGLE_200,
        CONF_HOST: "192.168.1.56",
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "654321",
        CONF_HARDWARE_ADDRESS: "meter-2",
    }


async def test_reconfigure_eagle_100(hass: HomeAssistant) -> None:
    """Test reconfigure updates an EAGLE-100 entry."""
    entry = _mock_reconfigure_entry(hass)
    result = await entry.start_reconfigure_flow(hass)

    with (
        patch(
            "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
            return_value=(TYPE_EAGLE_100, None),
        ),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "654321",
                CONF_HOST: "192.168.1.56",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_TYPE: TYPE_EAGLE_100,
        CONF_HOST: "192.168.1.56",
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "654321",
        CONF_HARDWARE_ADDRESS: None,
    }


async def test_reconfigure_unique_id_mismatch(hass: HomeAssistant) -> None:
    """Test reconfigure aborts when Cloud ID changes."""
    entry = _mock_reconfigure_entry(hass)
    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
    ) as mock_get_type:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "different",
                CONF_INSTALL_CODE: "654321",
                CONF_HOST: "192.168.1.56",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert len(mock_get_type.mock_calls) == 0
    assert entry.data[CONF_CLOUD_ID] == "abcdef"


@pytest.mark.parametrize(
    ("eagle_type", "hardware_address", "error"),
    [
        (None, None, "unknown_device_type"),
        (TYPE_EAGLE_200, None, "no_meters_connected"),
        ("UNSUPPORTED_DEVICE_TYPE", None, "unsupported_device_type"),
    ],
)
async def test_reconfigure_device_type_errors(
    hass: HomeAssistant,
    eagle_type: str | None,
    hardware_address: str | None,
    error: str,
) -> None:
    """Test reconfigure handles device type errors."""
    entry = _mock_reconfigure_entry(hass)
    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
        return_value=(eagle_type, hardware_address),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "654321",
                CONF_HOST: "192.168.1.56",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (InvalidAuth, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_reconfigure_connection_errors(
    hass: HomeAssistant, side_effect: type[Exception], error: str
) -> None:
    """Test reconfigure handles connection errors."""
    entry = _mock_reconfigure_entry(hass)
    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "654321",
                CONF_HOST: "192.168.1.56",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}
