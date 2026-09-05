"""Test the saj config flow."""

from unittest.mock import AsyncMock, MagicMock

import pysaj
import pytest

from homeassistant.components.saj.const import CONNECTION_TYPES, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TYPE, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_SERIAL_NUMBER, MOCK_USER_INPUT_ETHERNET, MOCK_USER_INPUT_WIFI

from tests.common import MockConfigEntry

IMPORT_DATA_ETHERNET = {
    CONF_HOST: "192.168.1.88",
    CONF_TYPE: CONNECTION_TYPES[0],
}

IMPORT_DATA_WIFI = {
    CONF_HOST: "192.168.1.88",
    CONF_TYPE: CONNECTION_TYPES[1],
    CONF_USERNAME: "u",
    CONF_PASSWORD: "p",
}


async def test_form_ethernet(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj_saj: MagicMock
) -> None:
    """Test we get the form for ethernet connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_INPUT_ETHERNET,
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SAJ Solar Inverter"
    result_data = result.get("data")
    assert result_data is not None
    assert result_data[CONF_HOST] == MOCK_USER_INPUT_ETHERNET[CONF_HOST]
    assert result_data[CONF_TYPE] == MOCK_USER_INPUT_ETHERNET[CONF_TYPE]
    assert not result_data.get(CONF_USERNAME)
    assert not result_data.get(CONF_PASSWORD)
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_wifi_open_network(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj_saj: MagicMock
) -> None:
    """Test WiFi without credentials when the device allows open access."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_USER_INPUT_WIFI[CONF_HOST],
            CONF_TYPE: MOCK_USER_INPUT_WIFI[CONF_TYPE],
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SAJ Solar Inverter"
    result_data = result.get("data")
    assert result_data is not None
    assert result_data[CONF_HOST] == MOCK_USER_INPUT_WIFI[CONF_HOST]
    assert result_data[CONF_TYPE] == MOCK_USER_INPUT_WIFI[CONF_TYPE]
    assert not result_data.get(CONF_USERNAME)
    assert not result_data.get(CONF_PASSWORD)
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_wifi_requires_credentials(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj_saj: MagicMock
) -> None:
    """Test WiFi flow when the first probe requires authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_pysaj_saj.read.side_effect = [
        pysaj.UnauthorizedException("Auth required"),
        True,
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_USER_INPUT_WIFI[CONF_HOST],
            CONF_TYPE: MOCK_USER_INPUT_WIFI[CONF_TYPE],
        },
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "device_credentials"
    assert result.get("errors") is None

    mock_pysaj_saj.read.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: MOCK_USER_INPUT_WIFI[CONF_USERNAME],
            CONF_PASSWORD: MOCK_USER_INPUT_WIFI[CONF_PASSWORD],
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SAJ Solar Inverter"
    result_data = result.get("data")
    assert result_data is not None
    assert result_data == MOCK_USER_INPUT_WIFI
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_missing_serial_number(
    hass: HomeAssistant, mock_pysaj_saj: MagicMock
) -> None:
    """Test we reject devices that respond but do not expose a serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_pysaj_saj.serialnumber = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_INPUT_ETHERNET,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}

    # Recover on the same flow once the device responds correctly.
    mock_pysaj_saj.serialnumber = MOCK_SERIAL_NUMBER
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_INPUT_ETHERNET,
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_form_wifi_probe_fails_shows_user_error(
    hass: HomeAssistant, mock_pysaj_saj: MagicMock
) -> None:
    """Test WiFi: failed probe (not SAJ / wrong host) keeps the user on host step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_pysaj_saj.read.side_effect = pysaj.UnexpectedResponseException("not a saj")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_USER_INPUT_WIFI[CONF_HOST],
            CONF_TYPE: MOCK_USER_INPUT_WIFI[CONF_TYPE],
        },
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}

    # Recover without restarting the flow once the probe works.
    mock_pysaj_saj.read.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_USER_INPUT_WIFI[CONF_HOST],
            CONF_TYPE: MOCK_USER_INPUT_WIFI[CONF_TYPE],
        },
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (pysaj.UnexpectedResponseException("Connection failed"), "cannot_connect"),
        (pysaj.UnauthorizedException("Auth failed"), "cannot_connect"),
        (Exception("Unknown error"), "cannot_connect"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
    mock_pysaj_saj: MagicMock,
) -> None:
    """Test we handle exceptions during form submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_pysaj_saj.read.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_INPUT_ETHERNET,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": error}

    # Recover once the inverter responds.
    mock_pysaj_saj.read.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_INPUT_ETHERNET,
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_pysaj_saj: MagicMock,
) -> None:
    """Test starting a flow by user when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT_ETHERNET,
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_import_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj_saj: MagicMock
) -> None:
    """Test YAML import creates a config entry."""
    data = {
        CONF_HOST: "192.168.1.88",
        CONF_TYPE: CONNECTION_TYPES[0],
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=data,
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SAJ Solar Inverter"
    assert result.get("data") == {
        **data,
        CONF_USERNAME: None,
        CONF_PASSWORD: None,
    }
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER


@pytest.mark.parametrize(
    ("import_data", "exception", "abort_reason"),
    [
        pytest.param(
            IMPORT_DATA_ETHERNET,
            pysaj.UnexpectedResponseException("bad response"),
            "cannot_connect",
            id="unexpected_response",
        ),
        pytest.param(
            IMPORT_DATA_ETHERNET,
            pysaj.UnauthorizedException("auth failed"),
            "cannot_connect",
            id="unauthorized_ethernet",
        ),
        pytest.param(
            IMPORT_DATA_ETHERNET,
            Exception("Unknown error"),
            "cannot_connect",
            id="unexpected_error",
        ),
        pytest.param(
            IMPORT_DATA_WIFI,
            pysaj.UnauthorizedException("auth failed"),
            "invalid_auth",
            id="unauthorized_wifi",
        ),
    ],
)
async def test_import_aborts(
    hass: HomeAssistant,
    mock_pysaj_saj: MagicMock,
    import_data: dict[str, str],
    exception: Exception,
    abort_reason: str,
) -> None:
    """Test YAML import aborts for validation failures."""
    mock_pysaj_saj.read.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=import_data,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == abort_reason


async def test_import_aborts_read_failed(
    hass: HomeAssistant, mock_pysaj_saj: MagicMock
) -> None:
    """Test YAML import aborts when the inverter read returns false."""
    mock_pysaj_saj.read.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=IMPORT_DATA_ETHERNET,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


async def test_import_aborts_missing_serial(
    hass: HomeAssistant, mock_pysaj_saj: MagicMock
) -> None:
    """Test YAML import aborts when the device does not return a serial number."""
    mock_pysaj_saj.serialnumber = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=IMPORT_DATA_ETHERNET,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


async def test_import_already_configured_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pysaj_saj: MagicMock,
) -> None:
    """Test YAML import aborts when the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=IMPORT_DATA_ETHERNET,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
