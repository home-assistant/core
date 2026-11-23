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
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
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


@pytest.mark.parametrize(
    ("flow_source", "step_id", "success_reason", "pass_data"),
    [
        (
            config_entries.SOURCE_RECONFIGURE,
            "reconfigure",
            "reconfigure_successful",
            False,
        ),
        (
            config_entries.SOURCE_REAUTH,
            "reauth_confirm",
            "reauth_successful",
            True,
        ),
    ],
)
@pytest.mark.parametrize(("side_effect", "expected_error"), CREDENTIAL_ERROR_CASES)
async def test_credential_update_error_recovery(
    hass: HomeAssistant,
    mock_sensor_client: MockAsyncClient,
    flow_source: str,
    step_id: str,
    success_reason: str,
    pass_data: bool,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reauth and reconfigure handle all credential errors and recover."""
    # pylint is generating a false-positive W7441 when assertions are parametrized
    # pylint: disable=home-assistant-tests-config-flow-error-recovery
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="test",
        unique_id=MOCK_CONFIG[CONF_USERNAME].casefold(),
    )
    config_entry.add_to_hass(hass)

    kwargs: dict[str, object] = {
        "context": {"source": flow_source, "entry_id": config_entry.entry_id}
    }
    if pass_data:
        kwargs["data"] = config_entry.data

    result1 = await hass.config_entries.flow.async_init(DOMAIN, **kwargs)
    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == step_id

    mock_sensor_client.login.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        user_input={
            CONF_USERNAME: MOCK_CONFIG[CONF_USERNAME],
            CONF_PASSWORD: "bad-password",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == step_id
    assert result2["errors"] == {"base": expected_error}

    mock_sensor_client.login.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            CONF_USERNAME: MOCK_CONFIG[CONF_USERNAME],
            CONF_PASSWORD: "fixed-password",
        },
    )

    assert result3["type"] == FlowResultType.ABORT
    assert result3["reason"] == success_reason
    assert config_entry.data[CONF_PASSWORD] == "fixed-password"


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
    hass: HomeAssistant,
    mock_sensor_client: MockAsyncClient,
    flow_source: str,
    step_id: str,
    pass_data: bool,
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

    mock_sensor_client.login.side_effect = KingspanInvalidCredentialsError
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

    mock_sensor_client.login.side_effect = None
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


async def test_reauth_wrong_account(hass: HomeAssistant) -> None:
    """Test reauth rejects credentials for a different account, then recovers."""
    # pylint is generating a false-positive W7441
    # pylint: disable=home-assistant-tests-config-flow-error-recovery
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="test",
        unique_id=MOCK_CONFIG[CONF_USERNAME].casefold(),
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)

    # Attempt reauth with the wrong account
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "different_account@example.com",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_account"}

    # Recover with the correct account
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: MOCK_CONFIG[CONF_USERNAME],
            CONF_PASSWORD: "fixed-password",
        },
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PASSWORD] == "fixed-password"


async def test_reconfigure_unique_id_mismatch(hass: HomeAssistant) -> None:
    """Test reconfigure aborts when the username belongs to a different account."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="test",
        unique_id=MOCK_CONFIG[CONF_USERNAME].casefold(),
    )
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "different_account@example.com",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "unique_id_mismatch"
    assert config_entry.data == MOCK_CONFIG
