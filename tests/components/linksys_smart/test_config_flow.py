"""Test Linksys Smart Wi-Fi config flow."""

from unittest.mock import AsyncMock, patch

from jnap import GetDeviceInfoResponse, JNAPError, JNAPUnauthorizedError

from homeassistant import config_entries
from homeassistant.components.linksys_smart import config_flow as linksys_config_flow
from homeassistant.components.linksys_smart.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

SERIAL = "38U10M37B21541"

_GOOD_CLIENT = {
    "get_device_info": AsyncMock(
        return_value=GetDeviceInfoResponse(
            description="Velop AX4200 WiFi 6 System", serial_number=SERIAL
        )
    ),
    "get_devices": AsyncMock(),
}


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Velop AX4200 WiFi 6 System"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.multiple(
        "jnap.JNAPClient",
        get_device_info=AsyncMock(),
        get_devices=AsyncMock(side_effect=JNAPUnauthorizedError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Velop AX4200 WiFi 6 System"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.multiple(
        "jnap.JNAPClient",
        get_device_info=AsyncMock(side_effect=JNAPError),
    ):
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

    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Velop AX4200 WiFi 6 System"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect_on_get_devices_error(hass: HomeAssistant) -> None:
    """Test we handle JNAPError from get_devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.multiple(
        "jnap.JNAPClient",
        get_device_info=AsyncMock(
            return_value=GetDeviceInfoResponse(
                description="Velop AX4200 WiFi 6 System", serial_number=SERIAL
            )
        ),
        get_devices=AsyncMock(side_effect=JNAPError),
    ):
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


async def test_form_unknown_error_on_get_devices_error(hass: HomeAssistant) -> None:
    """Test we surface unexpected errors from get_devices as unknown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch.object(linksys_config_flow._LOGGER, "exception") as mock_exception,
        patch.multiple(
            "jnap.JNAPClient",
            get_device_info=AsyncMock(
                return_value=GetDeviceInfoResponse(
                    description="Velop AX4200 WiFi 6 System", serial_number=SERIAL
                )
            ),
            get_devices=AsyncMock(side_effect=Exception),
        ),
    ):
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


async def test_user_flow_aborts_already_configured(hass: HomeAssistant) -> None:
    """Test that the user flow aborts when the serial number matches an existing entry."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={CONF_HOST: "1.1.1.1", CONF_PASSWORD: "old-password"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
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
