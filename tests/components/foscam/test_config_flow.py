"""Test the Foscam config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.foscam import config_flow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import setup_mock_foscam_camera
from .const import CAMERA_NAME, INVALID_RESPONSE_CONFIG, VALID_CONFIG

from tests.common import MockConfigEntry


async def test_user_valid(hass: HomeAssistant) -> None:
    """Test valid config from user input."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.foscam.config_flow.FoscamCamera",
        ) as mock_foscam_camera,
        patch(
            "homeassistant.components.foscam.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        setup_mock_foscam_camera(mock_foscam_camera)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == CAMERA_NAME
        assert result["data"] == VALID_CONFIG

        assert len(mock_setup_entry.mock_calls) == 1


async def test_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth from user input."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)

        invalid_user = VALID_CONFIG.copy()
        invalid_user[config_flow.CONF_USERNAME] = "invalid"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            invalid_user,
        )

        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error from user input."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)

        invalid_host = VALID_CONFIG.copy()
        invalid_host[config_flow.CONF_HOST] = "127.0.0.1"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            invalid_host,
        )

        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_user_invalid_response(hass: HomeAssistant) -> None:
    """Test we handle invalid response error from user input."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)

        invalid_response = VALID_CONFIG.copy()
        invalid_response[config_flow.CONF_USERNAME] = INVALID_RESPONSE_CONFIG[
            config_flow.CONF_USERNAME
        ]

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            invalid_response,
        )

        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_response"}


async def test_user_already_configured(hass: HomeAssistant) -> None:
    """Test we handle already configured from user input."""

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data=VALID_CONFIG,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera:
        setup_mock_foscam_camera(mock_foscam_camera)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_user_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown exceptions from user input."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.foscam.config_flow.FoscamCamera",
    ) as mock_foscam_camera:
        mock_foscam_camera.side_effect = Exception("test")

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
