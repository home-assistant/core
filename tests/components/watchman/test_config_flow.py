"""Test Kingspan Watchman SENSiT config flow."""

from connectsensor.exceptions import (
    KingspanAPIError,
    KingspanErrorCode,
    KingspanInvalidCredentialsError,
    KingspanNoDataError,
    KingspanTimeoutError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.watchman.config_flow import SENSiTFlowHandler
from homeassistant.components.watchman.const import DEFAULT_OIL_ENERGY_DENSITY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MockAsyncClient
from .const import MOCK_CONFIG

pytestmark = pytest.mark.usefixtures("mock_sensor_client")

CREDENTIAL_ERROR_CASES: list[tuple[Exception, str]] = [
    (
        KingspanInvalidCredentialsError("test bad auth"),
        KingspanErrorCode.AUTH_FAILED.value,
    ),
    (
        KingspanAPIError("cannot connect", KingspanErrorCode.CANNOT_CONNECT),
        KingspanErrorCode.CANNOT_CONNECT.value,
    ),
    (
        KingspanTimeoutError("timeout"),
        KingspanErrorCode.TIMEOUT.value,
    ),
    (
        KingspanNoDataError("no level data"),
        KingspanErrorCode.NO_DATA.value,
    ),
    (
        Exception("unknown"),
        KingspanErrorCode.UNKNOWN.value,
    ),
]


async def test_successful_config_flow(hass: HomeAssistant) -> None:
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == MOCK_CONFIG
    assert result["result"]
    assert result["result"].unique_id == "test@example.com"


def test_flow_matching_is_never_true() -> None:
    """The flow helper should report no match for unrelated flows."""
    flow = SENSiTFlowHandler()

    assert not flow.is_matching(object())
    assert not flow.is_matching(SENSiTFlowHandler())


@pytest.mark.parametrize(("side_effect", "expected_error"), CREDENTIAL_ERROR_CASES)
async def test_failed_config_flow(
    hass: HomeAssistant,
    mock_sensor_client: MockAsyncClient,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test user config flow handles all credential errors and recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_sensor_client.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    mock_sensor_client.login.side_effect = None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == MOCK_CONFIG


async def test_duplicate_config_flow_aborts(hass: HomeAssistant) -> None:
    """A second config flow for the same username should abort as already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id=MOCK_CONFIG["username"].casefold(),
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("initial_options", "user_input", "expected_options"),
    [
        (
            {},
            {},
            {
                "oil_energy_density": DEFAULT_OIL_ENERGY_DENSITY,
                "usage_window": 14,
            },
        ),
        (
            {},
            {"usage_window": 28},
            {
                "oil_energy_density": DEFAULT_OIL_ENERGY_DENSITY,
                "usage_window": 28,
            },
        ),
        (
            {
                "usage_window": 28,
                "oil_energy_density": 10.2,
            },
            {
                "usage_window": 14,
                "oil_energy_density": 10.5,
            },
            {
                "oil_energy_density": 10.5,
                "usage_window": 14,
            },
        ),
    ],
)
async def test_options_flows(
    hass: HomeAssistant, initial_options, user_input, expected_options
) -> None:
    """Test options flows with varying initial states and user inputs."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=initial_options, entry_id="test"
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result1 = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result1["flow_id"],
        user_input=user_input,
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert config_entry.options == expected_options
