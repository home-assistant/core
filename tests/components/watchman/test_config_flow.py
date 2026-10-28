"""Test Kingspan Watchman SENSiT config flow."""

from unittest.mock import patch

from connectsensor.exceptions import (
    KingspanErrorCode,
    KingspanInvalidCredentialsError,
    KingspanNoDataError,
    KingspanTimeoutError,
)
import pytest
import pytest_asyncio
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.watchman.config_flow import SENSiTFlowHandler
from homeassistant.components.watchman.const import DEFAULT_OIL_ENERGY_DENSITY, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG


@pytest_asyncio.fixture(autouse=True)  # pyright: ignore[reportArgumentType]
def bypass_setup_fixture():
    """Prevent setup and globally mock login to succeed for standard flow testing."""
    with (
        patch(
            "homeassistant.components.watchman.async_setup_entry",
            return_value=True,
        ),
        patch(
            "connectsensor.client.AsyncSensorClient.login",
            return_value=None,
        ),
    ):
        yield


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


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (
            KingspanInvalidCredentialsError("test bad auth"),
            KingspanErrorCode.AUTH_FAILED.value,
        ),
        (KingspanTimeoutError("timeout"), KingspanErrorCode.TIMEOUT.value),
        (KingspanNoDataError("no level data"), KingspanErrorCode.NO_DATA.value),
        (Exception("unknown"), KingspanErrorCode.UNKNOWN.value),
    ],
)
async def test_failed_config_flow(
    hass: HomeAssistant, side_effect, expected_error
) -> None:
    """Test a failed config flow due to credential validation failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Locally mock to override the fixture success
    with patch("connectsensor.client.AsyncSensorClient.login", side_effect=side_effect):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Recover from error
    with patch("connectsensor.client.AsyncSensorClient.login", return_value=None):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY


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


@pytest.mark.parametrize(
    ("flow_source", "step_id", "success_reason", "pass_data"),
    [
        (
            config_entries.SOURCE_RECONFIGURE,
            "reconfigure",
            "reconfigure_successful",
            False,
        ),
        (config_entries.SOURCE_REAUTH, "reauth_confirm", "reauth_successful", True),
    ],
)
async def test_credential_update_success(
    hass: HomeAssistant, flow_source, step_id, success_reason, pass_data
) -> None:
    """Test reauth and reconfigure flows successfully update the password and abort."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="test",
        unique_id=MOCK_CONFIG[CONF_USERNAME],
    )
    config_entry.add_to_hass(hass)

    kwargs = {"context": {"source": flow_source, "entry_id": config_entry.entry_id}}
    if pass_data:
        kwargs["data"] = config_entry.data

    result1 = await hass.config_entries.flow.async_init(DOMAIN, **kwargs)
    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == step_id

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        user_input={
            CONF_USERNAME: MOCK_CONFIG[CONF_USERNAME],
            CONF_PASSWORD: "new-password",
        },
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == success_reason
    assert config_entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.parametrize(
    ("flow_source", "step_id", "pass_data"),
    [
        (config_entries.SOURCE_RECONFIGURE, "reconfigure", False),
        (config_entries.SOURCE_REAUTH, "reauth_confirm", True),
    ],
)
async def test_credential_update_invalid_auth(
    hass: HomeAssistant, flow_source, step_id, pass_data
) -> None:
    """Test reauth and reconfigure steps handle invalid credentials correctly."""
    # pylint is generating a false-positive W7441
    # pylint: disable=home-assistant-tests-config-flow-error-recovery
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="test",
        unique_id=MOCK_CONFIG[CONF_USERNAME],
    )
    config_entry.add_to_hass(hass)

    kwargs = {"context": {"source": flow_source, "entry_id": config_entry.entry_id}}
    if pass_data:
        kwargs["data"] = config_entry.data

    result1 = await hass.config_entries.flow.async_init(DOMAIN, **kwargs)
    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == step_id

    with patch(
        "connectsensor.client.AsyncSensorClient.login",
        side_effect=KingspanInvalidCredentialsError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            user_input={
                CONF_USERNAME: MOCK_CONFIG[CONF_USERNAME],
                CONF_PASSWORD: "bad-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == step_id
    assert result2["errors"] == {"base": KingspanErrorCode.AUTH_FAILED.value}

    # Recover from error
    with patch("connectsensor.client.AsyncSensorClient.login", return_value=None):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={
                CONF_USERNAME: MOCK_CONFIG[CONF_USERNAME],
                CONF_PASSWORD: "fixed-password",
            },
        )

    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == (
        "reconfigure_successful" if step_id == "reconfigure" else "reauth_successful"
    )
