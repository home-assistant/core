"""Test Linksys Smart Wi-Fi config flow."""

from unittest.mock import AsyncMock, patch

from jnap import JNAPError, JNAPUnauthorizedError
import pytest

from homeassistant import config_entries
from homeassistant.components.linksys_smart import config_flow as linksys_config_flow
from homeassistant.components.linksys_smart.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import SERIAL

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_jnap_client: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Velop AX4200 WiFi 6 System"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("faulty_attr", "side_effect", "expected_error"),
    [
        pytest.param(
            "get_devices", JNAPUnauthorizedError, "invalid_auth", id="invalid_auth"
        ),
        pytest.param(
            "get_device_info", JNAPError, "cannot_connect", id="cannot_connect"
        ),
    ],
)
async def test_form_recovers_from_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_jnap_client: AsyncMock,
    faulty_attr: str,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test the form shows an error, then succeeds once the router recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    getattr(mock_jnap_client, faulty_attr).side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    getattr(mock_jnap_client, faulty_attr).side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Velop AX4200 WiFi 6 System"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect_on_get_devices_error(
    hass: HomeAssistant, mock_jnap_client: AsyncMock
) -> None:
    """Test we handle JNAPError from get_devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_jnap_client.get_devices.side_effect = JNAPError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error_on_get_devices_error(
    hass: HomeAssistant, mock_jnap_client: AsyncMock
) -> None:
    """Test we surface unexpected errors from get_devices as unknown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_jnap_client.get_devices.side_effect = Exception
    with patch.object(linksys_config_flow._LOGGER, "exception") as mock_exception:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    mock_exception.assert_called_once_with("Unexpected exception")


async def test_user_flow_aborts_already_configured(
    hass: HomeAssistant, mock_jnap_client: AsyncMock
) -> None:
    """Test that the user flow aborts when the serial number matches an existing entry."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={CONF_HOST: "1.1.1.1", CONF_PASSWORD: "old-password"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
