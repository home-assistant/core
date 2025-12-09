"""Test the Hikvision config flow."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    TEST_DEVICE_ID,
    TEST_DEVICE_NAME,
    TEST_HOST,
    TEST_PASSWORD,
    TEST_PORT,
    TEST_USERNAME,
)

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hikcamera_config_flow: MagicMock,
) -> None:
    """Test we get the form and can create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_DEVICE_NAME
    assert result2["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_SSL: False,
    }


async def test_form_with_ssl(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hikcamera_config_flow: MagicMock,
) -> None:
    """Test form submission with SSL enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: 443,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: True,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_SSL] is True
    assert result2["data"][CONF_PORT] == 443


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hikcamera_config_flow: MagicMock,
) -> None:
    """Test we handle cannot connect error."""
    mock_hikcamera_config_flow.return_value.get_id = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_exception(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hikcamera_config_flow: MagicMock,
) -> None:
    """Test we handle exception during connection."""
    mock_hikcamera_config_flow.side_effect = Exception("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hikcamera_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we handle already configured devices."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hikcamera_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthorization flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new_user",
            CONF_PASSWORD: "new_password",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "new_user"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hikcamera_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with connection error."""
    mock_config_entry.add_to_hass(hass)
    mock_hikcamera_config_flow.return_value.get_id = None

    result = await mock_config_entry.start_reauth_flow(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new_user",
            CONF_PASSWORD: "new_password",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_wrong_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hikcamera_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with wrong device ID."""
    mock_config_entry.add_to_hass(hass)
    mock_hikcamera_config_flow.return_value.get_id = "different_device_id"

    result = await mock_config_entry.start_reauth_flow(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new_user",
            CONF_PASSWORD: "new_password",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "wrong_device"}


async def test_reauth_flow_exception(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hikcamera_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with exception."""
    mock_config_entry.add_to_hass(hass)
    mock_hikcamera_config_flow.side_effect = Exception("Connection failed")

    result = await mock_config_entry.start_reauth_flow(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new_user",
            CONF_PASSWORD: "new_password",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_recovery_from_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hikcamera_config_flow: MagicMock,
) -> None:
    """Test we can recover from a connection error."""
    mock_hikcamera_config_flow.return_value.get_id = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    # Now recover
    mock_hikcamera_config_flow.return_value.get_id = TEST_DEVICE_ID

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
