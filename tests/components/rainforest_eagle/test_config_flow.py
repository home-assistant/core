"""Test the Rainforest Eagle config flow."""

from unittest.mock import MagicMock, patch

from probatio import to_field_list
import pytest
from pytest_homeassistant.common import MockConfigEntry

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
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv

RECONFIGURE_INPUT = {CONF_INSTALL_CODE: "654321", CONF_HOST: "192.168.1.56"}


def _mock_reconfigure_entry(
    hass: HomeAssistant, title: str = "abcdef"
) -> MockConfigEntry:
    """Add a mock config entry for reconfigure tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        unique_id="abcdef",
        data={
            CONF_TYPE: TYPE_EAGLE_200,
            CONF_HOST: "192.168.1.55",
            CONF_CLOUD_ID: "abcdef",
            CONF_INSTALL_CODE: "123456",
            CONF_HARDWARE_ADDRESS: "meter-1",
            "extra_data": "preserved",
        },
    )
    entry.add_to_hass(hass)
    return entry


def _meter(hardware_address: str, connection_status: str) -> MagicMock:
    """Return a meter as reported by EagleHub.get_device_list."""
    return MagicMock(
        hardware_address=hardware_address, connection_status=connection_status
    )


async def _async_configure_success(
    hass: HomeAssistant, flow_id: str
) -> ConfigFlowResult:
    """Configure the user step with a connected EAGLE-200 meter."""
    with (
        patch(
            "aioeagle.EagleHub.get_device_list",
            return_value=[
                MagicMock(hardware_address="meter-1", connection_status="Connected")
            ],
        ),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )
        await hass.async_block_till_done()
    return result


async def _async_reconfigure_success(
    hass: HomeAssistant, flow_id: str
) -> ConfigFlowResult:
    """Configure the reconfigure step with a connected EAGLE-200 meter."""
    with (
        patch(
            "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
            return_value=(TYPE_EAGLE_200, "meter-2"),
        ),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, RECONFIGURE_INPUT
        )
        await hass.async_block_till_done()
    return result


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
            return_value=None,
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

    result = await _async_configure_success(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


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

    result = await _async_configure_success(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


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
            return_value=None,
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


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test setup aborts when Cloud ID is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        title="abcdef",
        unique_id="abcdef",
        data={
            CONF_TYPE: TYPE_EAGLE_200,
            CONF_HOST: "rainforest-eagle.local",
            CONF_CLOUD_ID: "abcdef",
            CONF_INSTALL_CODE: "123456",
            CONF_HARDWARE_ADDRESS: "meter-1",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
    ) as mock_get_type:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLOUD_ID: "abcdef",
                CONF_INSTALL_CODE: "123456",
                CONF_HOST: "192.168.1.55",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_get_type.assert_not_called()


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

    result = await _async_configure_success(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


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

    result = await _async_configure_success(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


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

    result = await _async_configure_success(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


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

    result = await _async_configure_success(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


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

    result = await _async_configure_success(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_form(hass: HomeAssistant) -> None:
    """Test reconfigure displays the saved Cloud ID as read-only."""
    entry = _mock_reconfigure_entry(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    fields = to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    cloud_id_field = next(
        field
        for field in fields
        if isinstance(field, dict) and field["name"] == CONF_CLOUD_ID
    )
    assert cloud_id_field["default"] == entry.data[CONF_CLOUD_ID]
    assert cloud_id_field["selector"]["text"]["read_only"] is True


@pytest.mark.parametrize(
    ("eagle_type", "hardware_address", "title", "user_input"),
    [
        pytest.param(
            TYPE_EAGLE_200, "meter-2", "abcdef", RECONFIGURE_INPUT, id="eagle_200"
        ),
        pytest.param(TYPE_EAGLE_100, None, "abcdef", RECONFIGURE_INPUT, id="eagle_100"),
        pytest.param(
            TYPE_EAGLE_200,
            "meter-2",
            "Garage eagle",
            {**RECONFIGURE_INPUT, CONF_CLOUD_ID: "different"},
            id="ignores_submitted_cloud_id_and_keeps_custom_title",
        ),
    ],
)
async def test_reconfigure(
    hass: HomeAssistant,
    eagle_type: str,
    hardware_address: str | None,
    title: str,
    user_input: dict[str, str],
) -> None:
    """Test reconfigure updates the connection while preserving identity."""
    entry = _mock_reconfigure_entry(hass, title=title)
    result = await entry.start_reconfigure_flow(hass)

    with (
        patch(
            "homeassistant.components.rainforest_eagle.config_flow.async_get_type",
            return_value=(eagle_type, hardware_address),
        ) as mock_get_type,
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    mock_get_type.assert_awaited_once_with(
        hass,
        "abcdef",
        RECONFIGURE_INPUT[CONF_INSTALL_CODE],
        RECONFIGURE_INPUT[CONF_HOST],
        "meter-1",
    )
    assert entry.unique_id == "abcdef"
    assert entry.title == title
    assert entry.data == {
        **RECONFIGURE_INPUT,
        CONF_TYPE: eagle_type,
        CONF_CLOUD_ID: "abcdef",
        CONF_HARDWARE_ADDRESS: hardware_address,
        "extra_data": "preserved",
    }


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
            result["flow_id"], RECONFIGURE_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    result = await _async_reconfigure_success(hass, result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


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
            result["flow_id"], RECONFIGURE_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    result = await _async_reconfigure_success(hass, result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    ("meters", "expected_hardware_address"),
    [
        pytest.param(
            [_meter("meter-2", "Connected"), _meter("meter-1", "Connected")],
            "meter-1",
            id="keeps_configured_meter",
        ),
        pytest.param(
            [_meter("meter-1", "Not Joined"), _meter("meter-2", "Connected")],
            "meter-2",
            id="falls_back_when_configured_meter_unavailable",
        ),
    ],
)
async def test_reconfigure_meter_selection(
    hass: HomeAssistant,
    meters: list[MagicMock],
    expected_hardware_address: str,
) -> None:
    """Test reconfigure prefers the configured meter over the first connected one."""
    entry = _mock_reconfigure_entry(hass)
    result = await entry.start_reconfigure_flow(hass)

    with (
        patch("aioeagle.EagleHub.get_device_list", return_value=meters),
        patch(
            "homeassistant.components.rainforest_eagle.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], RECONFIGURE_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_CLOUD_ID] == "abcdef"
    assert entry.data[CONF_HARDWARE_ADDRESS] == expected_hardware_address
