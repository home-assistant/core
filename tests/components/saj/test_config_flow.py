"""Test the saj config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pysaj
import pytest

from homeassistant.components.saj.const import CONNECTION_TYPES, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_SERIAL_NUMBER, MOCK_USER_INPUT_ETHERNET, MOCK_USER_INPUT_WIFI

from tests.common import MockConfigEntry


async def test_form_ethernet(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj: MagicMock
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
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SAJ Solar Inverter"
    result_data = result.get("data")
    assert result_data is not None
    assert result_data[CONF_HOST] == MOCK_USER_INPUT_ETHERNET[CONF_HOST]
    assert result_data[CONF_TYPE] == MOCK_USER_INPUT_ETHERNET[CONF_TYPE]
    assert result_data.get(CONF_USERNAME, "") == ""
    assert result_data.get(CONF_PASSWORD, "") == ""
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_wifi_open_network(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj: MagicMock
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
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "SAJ Solar Inverter"
    result_data = result.get("data")
    assert result_data is not None
    assert result_data[CONF_HOST] == MOCK_USER_INPUT_WIFI[CONF_HOST]
    assert result_data[CONF_TYPE] == MOCK_USER_INPUT_WIFI[CONF_TYPE]
    assert result_data[CONF_USERNAME] == ""
    assert result_data[CONF_PASSWORD] == ""
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_wifi_requires_credentials(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test WiFi flow when the first probe requires authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = MOCK_SERIAL_NUMBER
        saj_instance.read = AsyncMock(
            side_effect=[
                pysaj.UnauthorizedException("Auth required"),
                True,
            ]
        )
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
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

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = MOCK_SERIAL_NUMBER
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_NAME: "Roof Inverter",
                    CONF_USERNAME: MOCK_USER_INPUT_WIFI[CONF_USERNAME],
                    CONF_PASSWORD: MOCK_USER_INPUT_WIFI[CONF_PASSWORD],
                },
            )

    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Roof Inverter"
    result_data = result.get("data")
    assert result_data is not None
    assert result_data == MOCK_USER_INPUT_WIFI
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_missing_serial_number(
    hass: HomeAssistant,
) -> None:
    """Test we reject devices that respond but do not expose a serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = None
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_USER_INPUT_ETHERNET,
            )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_form_wifi_probe_fails_shows_user_error(
    hass: HomeAssistant,
) -> None:
    """Test WiFi: failed probe (not SAJ / wrong host) keeps the user on host step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(
            side_effect=pysaj.UnexpectedResponseException("not a saj")
        )
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
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
) -> None:
    """Test we handle exceptions during form submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(side_effect=exception)
        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_USER_INPUT_ETHERNET,
            )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": error}


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj: MagicMock
) -> None:
    """Test starting a flow by user when already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_INPUT_ETHERNET, unique_id=MOCK_SERIAL_NUMBER
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = MOCK_SERIAL_NUMBER
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=MOCK_USER_INPUT_ETHERNET,
            )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_import_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pysaj: MagicMock
) -> None:
    """Test YAML import creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.1.88",
            CONF_TYPE: CONNECTION_TYPES[0],
        },
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == MOCK_SERIAL_NUMBER


async def test_import_invalid_auth(hass: HomeAssistant) -> None:
    """Test YAML import aborts when credentials are rejected."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(
            side_effect=pysaj.UnauthorizedException("auth failed")
        )
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_HOST: "192.168.1.88",
                    CONF_TYPE: CONNECTION_TYPES[1],
                    CONF_USERNAME: "u",
                    CONF_PASSWORD: "p",
                },
            )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "invalid_auth"


async def test_import_cannot_connect(hass: HomeAssistant) -> None:
    """Test YAML import aborts when the inverter cannot be reached."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(
            side_effect=pysaj.UnexpectedResponseException("bad response")
        )
        saj_cls.return_value = saj_instance
        with patch("pysaj.Sensors"):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_HOST: "192.168.1.88",
                    CONF_TYPE: CONNECTION_TYPES[0],
                },
            )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"
