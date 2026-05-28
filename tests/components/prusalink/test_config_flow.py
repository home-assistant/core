"""Test the PrusaLink config flow."""

from typing import Any
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.prusalink.config_flow import InvalidAuth
from homeassistant.components.prusalink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_version_api: dict[str, str],
    mock_info_api: dict[str, Any],
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.prusalink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "http://1.1.1.1/",
                "username": "abcdefg",
                "password": "abcdefg",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "PrusaXL"
    assert result2["data"] == {
        "host": "http://1.1.1.1",
        "username": "abcdefg",
        "password": "abcdefg",
    }
    assert result2["result"].unique_id == "serial-1337"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_mk3(
    hass: HomeAssistant,
    mock_version_api: dict[str, str],
    mock_info_api: dict[str, Any],
) -> None:
    """Test it works for MK2/MK3."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_version_api["api"] = "0.9.0-legacy"
    mock_version_api["server"] = "0.7.2"
    mock_version_api["original"] = "PrusaLink I3MK3S"

    with patch(
        "homeassistant.components.prusalink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "http://1.1.1.1/",
                "username": "abcdefg",
                "password": "abcdefg",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_version_api: dict[str, str],
    mock_info_api: dict[str, Any],
) -> None:
    """Test we abort if the printer is already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="serial-1337",
        data={"host": "http://2.2.2.2", "username": "maker", "password": "secret"},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "abcdefg",
            "password": "abcdefg",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.prusalink.config_flow.PrusaLink.get_version",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "abcdefg",
                "password": "abcdefg",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.prusalink.config_flow.PrusaLink.get_version",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "abcdefg",
                "password": "abcdefg",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_too_low_version(hass: HomeAssistant, mock_version_api) -> None:
    """Test we handle too low API version."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_version_api["api"] = "1.2.0"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "abcdefg",
            "password": "abcdefg",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "not_supported"}


async def test_form_invalid_version_2(hass: HomeAssistant, mock_version_api) -> None:
    """Test we handle invalid version."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_version_api["api"] = "i am not a version"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "abcdefg",
            "password": "abcdefg",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "not_supported"}


async def test_form_invalid_mk3_server_version(
    hass: HomeAssistant, mock_version_api
) -> None:
    """Test we handle invalid version for MK2/MK3."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_version_api["api"] = "0.7.2"
    mock_version_api["server"] = "i am not a version"
    mock_version_api["original"] = "PrusaLink I3MK3S"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "username": "abcdefg",
            "password": "abcdefg",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "not_supported"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.prusalink.config_flow.PrusaLink.get_version",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "abcdefg",
                "password": "abcdefg",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect_get_info(
    hass: HomeAssistant,
    mock_version_api: dict[str, str],
) -> None:
    """Test we handle cannot connect error from info endpoint."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.prusalink.config_flow.PrusaLink.get_info",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "abcdefg",
                "password": "abcdefg",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
