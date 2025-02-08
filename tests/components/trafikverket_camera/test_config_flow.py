"""Test the Trafikverket Camera config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytrafikverket import (
    CameraInfoModel,
    InvalidAuthentication,
    NoCameraFound,
    UnknownError,
)

from homeassistant import config_entries
from homeassistant.components.trafikverket_camera.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, get_camera: CameraInfoModel) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
            return_value=[get_camera],
        ),
        patch(
            "homeassistant.components.trafikverket_camera.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_LOCATION: "Test loc",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Camera"
    assert result2["data"] == {
        "api_key": "1234567890",
        "id": "1234",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert result2["result"].unique_id == "trafikverket_camera-1234"


async def test_form_multiple_cameras(
    hass: HomeAssistant,
    get_cameras: list[CameraInfoModel],
    get_camera2: CameraInfoModel,
) -> None:
    """Test we get the form with multiple cameras."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
        return_value=get_cameras,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_LOCATION: "Test loc",
            },
        )
        await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
            return_value=[get_camera2],
        ),
        patch(
            "homeassistant.components.trafikverket_camera.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ID: "5678",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Camera2"
    assert result["data"] == {
        "api_key": "1234567890",
        "id": "5678",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["result"].unique_id == "trafikverket_camera-5678"


async def test_form_no_location_data(
    hass: HomeAssistant, get_camera_no_location: CameraInfoModel
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
            return_value=[get_camera_no_location],
        ),
        patch(
            "homeassistant.components.trafikverket_camera.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_LOCATION: "Test Cam",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Camera"
    assert result2["data"] == {
        "api_key": "1234567890",
        "id": "1234",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert result2["result"].unique_id == "trafikverket_camera-1234"


@pytest.mark.parametrize(
    ("side_effect", "error_key", "base_error"),
    [
        (
            InvalidAuthentication,
            "base",
            "invalid_auth",
        ),
        (
            NoCameraFound,
            "location",
            "invalid_location",
        ),
        (
            UnknownError,
            "base",
            "cannot_connect",
        ),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant, side_effect: Exception, error_key: str, base_error: str
) -> None:
    """Test config flow errors."""
    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] is FlowResultType.FORM
    assert result4["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
        side_effect=side_effect,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
                CONF_LOCATION: "incorrect",
            },
        )

    assert result4["errors"] == {error_key: base_error}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_ID: "1234",
        },
        unique_id="1234",
        version=3,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
        ),
        patch(
            "homeassistant.components.trafikverket_camera.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        "api_key": "1234567891",
        "id": "1234",
    }


@pytest.mark.parametrize(
    ("side_effect", "error_key", "p_error"),
    [
        (
            InvalidAuthentication,
            "base",
            "invalid_auth",
        ),
        (
            NoCameraFound,
            "location",
            "invalid_location",
        ),
        (
            UnknownError,
            "base",
            "cannot_connect",
        ),
    ],
)
async def test_reauth_flow_error(
    hass: HomeAssistant, side_effect: Exception, error_key: str, p_error: str
) -> None:
    """Test a reauthentication flow with error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_ID: "1234",
        },
        unique_id="1234",
        version=3,
    )
    entry.add_to_hass(hass)
    await hass.async_block_till_done()

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567890"},
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {error_key: p_error}

    with (
        patch(
            "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
        ),
        patch(
            "homeassistant.components.trafikverket_camera.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        "api_key": "1234567891",
        "id": "1234",
    }


async def test_reconfigure_flow(
    hass: HomeAssistant,
    get_cameras: list[CameraInfoModel],
    get_camera2: CameraInfoModel,
) -> None:
    """Test a reconfigure flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_ID: "1234",
        },
        unique_id="1234",
        version=3,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
        return_value=get_cameras,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_LOCATION: "Test loc",
            },
        )
        await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
            return_value=[get_camera2],
        ),
        patch(
            "homeassistant.components.trafikverket_camera.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ID: "5678",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        "api_key": "1234567890",
        "id": "5678",
    }


@pytest.mark.parametrize(
    ("side_effect", "error_key", "p_error"),
    [
        (
            InvalidAuthentication,
            "base",
            "invalid_auth",
        ),
        (
            NoCameraFound,
            "location",
            "invalid_location",
        ),
        (
            UnknownError,
            "base",
            "cannot_connect",
        ),
    ],
)
async def test_reconfigure_flow_error(
    hass: HomeAssistant,
    get_camera: CameraInfoModel,
    side_effect: Exception,
    error_key: str,
    p_error: str,
) -> None:
    """Test a reauthentication flow with error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_ID: "1234",
        },
        unique_id="1234",
        version=3,
    )
    entry.add_to_hass(hass)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_LOCATION: "Test loc",
            },
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reconfigure"
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {error_key: p_error}

    with (
        patch(
            "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_cameras",
            return_value=[get_camera],
        ),
        patch(
            "homeassistant.components.trafikverket_camera.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567891",
                CONF_LOCATION: "Test loc",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_ID: "1234",
        CONF_API_KEY: "1234567891",
    }
