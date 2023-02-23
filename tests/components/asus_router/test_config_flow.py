"""Tests for the Asus Router configuration flow module."""

from socket import gaierror
from unittest.mock import AsyncMock, patch

from asusrouter import (
    AsusDevice,
    AsusRouterConnectionError,
    AsusRouterLoginBlockError,
    AsusRouterLoginError,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.asus_router.config_flow import (
    _async_check_connection,
    _async_process_step,
    _check_errors,
)
from homeassistant.components.asus_router.const import (
    BASE,
    DOMAIN,
    ERRORS,
    METHOD,
    NEXT,
    RESULT_CANNOT_RESOLVE,
    RESULT_CONNECTION_REFUSED,
    RESULT_ERROR,
    RESULT_LOGIN_BLOCKED,
    RESULT_SUCCESS,
    RESULT_UNKNOWN,
    RESULT_WRONG_CREDENTIALS,
    STEP_CREDENTIALS,
    STEP_FIND,
    STEP_FINISH,
    UNIQUE_ID,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Keys
CONTEXT = "context"
DATA = "data"
DUMMY = "dummy"
DUMMY_2 = "dummy_2"
FLOW_ID = "flow_id"
KEY_OPTIONS = "options"
STEP_ID = "step_id"
SOURCE = "source"
TITLE = "title"
TYPE = "type"

# Dummy values
HOST = "connect.asus_router.com"
IP = "192.168.1.1"
MAC = "AA:11:CC:00:BB:22"
SERIAL = "SeRiAlNo"

CONFIGS = {
    CONF_HOST: HOST,
}

OPTIONS = {
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "p455w0rd",
    CONF_PORT: 8443,
    CONF_SSL: True,
}

OPTIONS_UPDATE = {
    CONF_USERNAME: "Admin",
    CONF_PASSWORD: "p455w0rd",
    CONF_PORT: 8445,
    CONF_SSL: True,
}

STEPS = {
    STEP_FIND: {METHOD: AsyncMock(return_value=True), NEXT: STEP_CREDENTIALS},
    STEP_CREDENTIALS: {METHOD: AsyncMock(return_value=False), NEXT: STEP_FINISH},
    STEP_FINISH: {METHOD: AsyncMock(return_value=True)},
}

STEPS_TO_FAIL = {
    DUMMY: {NEXT: DUMMY_2},
    DUMMY_2: {METHOD: AsyncMock(return_value=True)},
}

PATCH_GET_HOST = patch(
    "homeassistant.components.asus_router.config_flow.socket.gethostbyname",
    return_value=IP,
)

PATCH_CHECK_CONNECTION = patch(
    "homeassistant.components.asus_router.config_flow._async_check_connection",
    return_value=OPTIONS,
)

PATCH_STEPS = patch(
    "homeassistant.components.asus_router.config_flow.ARFlowHandler._steps",
    return_value=STEPS,
)

PATCH_SETUP_ENTRY = patch(
    "homeassistant.components.asus_router.async_setup_entry",
    return_value=True,
)


class ARBridgeDummy:
    """Dummy AR bridge class."""

    def __init__(
        self,
        side_effect=None,
    ):
        """Initialize bridge dummy."""

        self.async_connect = AsyncMock(side_effect=side_effect)
        self.async_clean = AsyncMock()
        self.async_disconnect = AsyncMock()
        self.identity = AsusDevice(serial=SERIAL)


def patch_bridge(*, side_effect=None):
    """Mock connection to the bridge."""

    return patch(
        "homeassistant.components.asus_router.config_flow.ARBridge",
        return_value=ARBridgeDummy(side_effect=side_effect),
    )


@pytest.mark.parametrize(
    ("code", "check"),
    [
        (RESULT_CANNOT_RESOLVE, True),
        (RESULT_CONNECTION_REFUSED, True),
        (RESULT_ERROR, True),
        (RESULT_LOGIN_BLOCKED, True),
        (RESULT_SUCCESS, False),
        (RESULT_UNKNOWN, True),
        (RESULT_WRONG_CREDENTIALS, True),
    ],
)
def test_check_errors(code, check):
    """Test errors checking."""

    result = _check_errors(
        {
            BASE: code,
        }
    )

    assert result == check


async def test_check_connection_wo_host(hass: HomeAssistant):
    """Test connection check fail when no host provided."""

    result = await _async_check_connection(
        hass=hass,
        configs={},
        options=OPTIONS,
    )

    assert result[ERRORS] == RESULT_ERROR


@pytest.mark.parametrize(
    ("step", "error", "answer"),
    [
        (STEP_FIND, None, False),
        (STEP_FIND, {BASE: RESULT_ERROR}, True),
        (STEP_CREDENTIALS, None, True),
        (STEP_CREDENTIALS, {BASE: RESULT_ERROR}, False),
    ],
)
async def test_process_step(hass: HomeAssistant, step, error, answer):
    """Test the universal step selector with existing steps."""

    result = await _async_process_step(
        steps=STEPS,
        step=step,
        errors=error,
    )

    assert result == answer


@pytest.mark.parametrize(
    ("step", "error"),
    [
        (None, None),
        (DUMMY, {BASE: RESULT_ERROR}),
        (DUMMY_2, None),
    ],
)
async def test_process_step_fail(hass: HomeAssistant, step, error):
    """Test the universal step selector failing with non-existing steps."""

    with pytest.raises(ValueError):
        await _async_process_step(
            steps=STEPS_TO_FAIL,
            step=step,
            errors=error,
        )


async def test_step_user(hass: HomeAssistant):
    """Test complete user configuration."""

    with patch_bridge(), PATCH_GET_HOST:
        # Pass the first step as if device was successfully found
        flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={SOURCE: SOURCE_USER},
            data=CONFIGS,
        )

        # Confirm transfer to the next step (`credentials`)
        assert flow[TYPE] == data_entry_flow.FlowResultType.FORM
        assert flow[STEP_ID] == STEP_CREDENTIALS

        # Pass the step with successful connection to a device and confirming input
        result = await hass.config_entries.flow.async_configure(
            flow[FLOW_ID], user_input=OPTIONS
        )
        await hass.async_block_till_done()

        # Confirm creation of the entry with the correct input data
        # and data received from device
        assert result[TYPE] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result[DATA] == CONFIGS
        assert result[KEY_OPTIONS] == OPTIONS
        assert result[TITLE] == HOST
        assert result[CONTEXT][UNIQUE_ID] == SERIAL


async def test_step_find_fail(hass: HomeAssistant):
    """Test failing on the `find` step."""

    with patch(
        "homeassistant.components.asus_router.config_flow.socket.gethostbyname",
        side_effect=gaierror,
    ):
        # Fail on resolving hostname
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={SOURCE: SOURCE_USER},
            data=CONFIGS,
        )

        # Confirm that the correct error is returned
        assert result[TYPE] == data_entry_flow.FlowResultType.FORM
        assert result[STEP_ID] == STEP_FIND
        assert result[ERRORS] == {BASE: RESULT_CANNOT_RESOLVE}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AsusRouterLoginError, RESULT_WRONG_CREDENTIALS),
        (AsusRouterLoginBlockError, RESULT_LOGIN_BLOCKED),
        (AsusRouterConnectionError, RESULT_CONNECTION_REFUSED),
        (Exception, RESULT_UNKNOWN),
    ],
)
async def test_step_credentials_fail(hass: HomeAssistant, side_effect, error):
    """Test failing on the `credentials` step when not being able to connect to the device."""

    with patch_bridge(side_effect=side_effect), PATCH_GET_HOST:
        # Pass the first step as if device was successfully found
        flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={SOURCE: SOURCE_USER},
            data=CONFIGS,
        )

        # Try to write credentials and fail the check
        result = await hass.config_entries.flow.async_configure(
            flow[FLOW_ID], user_input=OPTIONS
        )

        # Confirm that correct errors were returned
        assert result[TYPE] == data_entry_flow.FlowResultType.FORM
        assert result[STEP_ID] == STEP_CREDENTIALS
        assert result[ERRORS] == {BASE: error}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""

    # Mock configuration entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIGS,
        options=OPTIONS,
    )
    config_entry.add_to_hass(hass)

    with PATCH_SETUP_ENTRY, patch_bridge():
        # Setup entry
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Load options flow
        options = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert options[TYPE] == data_entry_flow.FlowResultType.FORM
        assert options[STEP_ID] == STEP_CREDENTIALS

        # Update options
        result = await hass.config_entries.options.async_configure(
            options[FLOW_ID],
            user_input=OPTIONS_UPDATE,
        )

        # Confirm that updates were written
        assert result[TYPE] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert config_entry.options == OPTIONS_UPDATE


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AsusRouterLoginError, RESULT_WRONG_CREDENTIALS),
        (AsusRouterLoginBlockError, RESULT_LOGIN_BLOCKED),
        (AsusRouterConnectionError, RESULT_CONNECTION_REFUSED),
        (Exception, RESULT_UNKNOWN),
    ],
)
async def test_options_flow_fail(hass: HomeAssistant, side_effect, error) -> None:
    """Test options flow failing on not being able to connect to the device."""

    # Mock configuration entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIGS,
        options=OPTIONS,
    )
    config_entry.add_to_hass(hass)

    with PATCH_SETUP_ENTRY, patch_bridge(side_effect=side_effect):
        # Setup entry
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Load options flow
        options = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert options[TYPE] == data_entry_flow.FlowResultType.FORM
        assert options[STEP_ID] == STEP_CREDENTIALS

        # Update options
        result = await hass.config_entries.options.async_configure(
            options[FLOW_ID],
            user_input=OPTIONS_UPDATE,
        )

        # Confirm that updates were written
        assert result[TYPE] == data_entry_flow.FlowResultType.FORM
        assert result[ERRORS] == {BASE: error}
