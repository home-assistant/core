"""Tests for the Vivotek config flow."""

from unittest.mock import AsyncMock

from libpyvivotek.vivotek import VivotekCameraError
import pytest

from homeassistant.components.vivotek.camera import DEFAULT_FRAMERATE, DEFAULT_NAME
from homeassistant.components.vivotek.const import (
    CONF_FRAMERATE,
    CONF_SECURITY_LEVEL,
    CONF_STREAM_PATH,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_DATA = {
    CONF_IP_ADDRESS: "1.2.3.4",
    CONF_PORT: 80,
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "pass1234",
    CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
    CONF_SECURITY_LEVEL: "admin",
    CONF_STREAM_PATH: "/live.sdp",
}

IMPORT_DATA = {
    CONF_IP_ADDRESS: "1.2.3.4",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "pass1234",
    CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
    CONF_SECURITY_LEVEL: "admin",
    CONF_STREAM_PATH: "/live.sdp",
    CONF_FRAMERATE: DEFAULT_FRAMERATE,
}


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_vivotek_camera: AsyncMock
) -> None:
    """Test full user initiated flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == USER_DATA
    assert result["options"] == {CONF_FRAMERATE: DEFAULT_FRAMERATE}
    assert result["result"].unique_id == "11:22:33:44:55:66"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (VivotekCameraError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_user_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vivotek_camera: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test user initiated flow with exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_vivotek_camera.get_mac.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_vivotek_camera.get_mac.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_DATA
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test flow abort on duplicate entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_duplicate_entry_mac(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test flow abort on duplicate MAC address."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_DATA, CONF_IP_ADDRESS: "1.1.1.1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_vivotek_camera: AsyncMock
) -> None:
    """Test import initiated flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == USER_DATA
    assert result["options"] == {CONF_FRAMERATE: DEFAULT_FRAMERATE}
    assert result["result"].unique_id == "11:22:33:44:55:66"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (VivotekCameraError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_import_flow_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vivotek_camera: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test import initiated flow with exceptions."""
    mock_vivotek_camera.get_mac.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_import_flow_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test import initiated flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=IMPORT_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_duplicate_mac(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test import initiated flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**IMPORT_DATA, CONF_IP_ADDRESS: "1.1.1.1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    mock_vivotek_camera: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_FRAMERATE: 15,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_FRAMERATE] == 15
