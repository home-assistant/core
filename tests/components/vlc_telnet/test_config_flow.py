"""Test the VLC media player Telnet config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from aiovlc.exceptions import AuthError, ConnectError
import pytest

from homeassistant import config_entries
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.components.vlc_telnet.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("input_data", "entry_data"),
    [
        (
            {
                "password": "test-password",
                "host": "1.1.1.1",
                "port": 8888,
            },
            {
                "password": "test-password",
                "host": "1.1.1.1",
                "port": 8888,
            },
        ),
        (
            {
                "password": "test-password",
            },
            {
                "password": "test-password",
                "host": "localhost",
                "port": 4212,
            },
        ),
    ],
)
async def test_user_flow(
    hass: HomeAssistant, input_data: dict[str, Any], entry_data: dict[str, Any]
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch("homeassistant.components.vlc_telnet.config_flow.Client.connect"),
        patch("homeassistant.components.vlc_telnet.config_flow.Client.login"),
        patch("homeassistant.components.vlc_telnet.config_flow.Client.disconnect"),
        patch(
            "homeassistant.components.vlc_telnet.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            input_data,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == entry_data["host"]
    assert result["data"] == entry_data
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("source", [config_entries.SOURCE_USER])
async def test_abort_already_configured(hass: HomeAssistant, source: str) -> None:
    """Test we handle already configured host."""
    entry_data = {
        "password": "test-password",
        "host": "1.1.1.1",
        "port": 8888,
        "name": "custom name",
    }

    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=entry_data,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("source", [config_entries.SOURCE_USER])
@pytest.mark.parametrize(
    ("error", "connect_side_effect", "login_side_effect"),
    [
        ("invalid_auth", None, AuthError),
        ("cannot_connect", ConnectError, None),
        ("unknown", Exception, None),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    error: str,
    connect_side_effect: Exception | None,
    login_side_effect: Exception | None,
    source: str,
) -> None:
    """Test we handle form errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}
    )

    with (
        patch(
            "homeassistant.components.vlc_telnet.config_flow.Client.connect",
            side_effect=connect_side_effect,
        ),
        patch(
            "homeassistant.components.vlc_telnet.config_flow.Client.login",
            side_effect=login_side_effect,
        ),
        patch(
            "homeassistant.components.vlc_telnet.config_flow.Client.disconnect",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "test-password"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test successful reauth flow."""
    entry_data: dict[str, Any] = {
        "password": "old-password",
        "host": "1.1.1.1",
        "port": 8888,
        "name": "custom name",
    }

    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry_data,
    )

    with (
        patch("homeassistant.components.vlc_telnet.config_flow.Client.connect"),
        patch("homeassistant.components.vlc_telnet.config_flow.Client.login"),
        patch("homeassistant.components.vlc_telnet.config_flow.Client.disconnect"),
        patch(
            "homeassistant.components.vlc_telnet.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "new-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1
    assert dict(entry.data) == {**entry_data, "password": "new-password"}


@pytest.mark.parametrize(
    ("error", "connect_side_effect", "login_side_effect"),
    [
        ("invalid_auth", None, AuthError),
        ("cannot_connect", ConnectError, None),
        ("unknown", Exception, None),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    error: str,
    connect_side_effect: Exception | None,
    login_side_effect: Exception | None,
) -> None:
    """Test we handle reauth errors."""
    entry_data = {
        "password": "old-password",
        "host": "1.1.1.1",
        "port": 8888,
        "name": "custom name",
    }

    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry_data,
    )

    with (
        patch(
            "homeassistant.components.vlc_telnet.config_flow.Client.connect",
            side_effect=connect_side_effect,
        ),
        patch(
            "homeassistant.components.vlc_telnet.config_flow.Client.login",
            side_effect=login_side_effect,
        ),
        patch(
            "homeassistant.components.vlc_telnet.config_flow.Client.disconnect",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "test-password"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}


async def test_hassio_flow(hass: HomeAssistant) -> None:
    """Test successful hassio flow."""
    with (
        patch("homeassistant.components.vlc_telnet.config_flow.Client.connect"),
        patch("homeassistant.components.vlc_telnet.config_flow.Client.login"),
        patch("homeassistant.components.vlc_telnet.config_flow.Client.disconnect"),
        patch(
            "homeassistant.components.vlc_telnet.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        test_data = HassioServiceInfo(
            config={
                "password": "test-password",
                "host": "1.1.1.1",
                "port": 8888,
                "name": "custom name",
                "addon": "VLC",
            },
            name="VLC",
            slug="vlc",
            uuid="1234",
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HASSIO},
            data=test_data,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == test_data.config["name"]
        assert result2["data"] == test_data.config
        assert len(mock_setup_entry.mock_calls) == 1


async def test_hassio_already_configured(hass: HomeAssistant) -> None:
    """Test successful hassio flow."""

    entry_data = {
        "password": "test-password",
        "host": "1.1.1.1",
        "port": 8888,
        "name": "custom name",
        "addon": "vlc",
    }

    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id="hassio")
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(config=entry_data, name="VLC", slug="vlc", uuid="1234"),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT


@pytest.mark.parametrize(
    ("error", "connect_side_effect", "login_side_effect"),
    [
        ("invalid_auth", None, AuthError),
        ("cannot_connect", ConnectError, None),
        ("unknown", Exception, None),
    ],
)
async def test_hassio_errors(
    hass: HomeAssistant,
    error: str,
    connect_side_effect: Exception | None,
    login_side_effect: Exception | None,
) -> None:
    """Test we handle hassio errors."""
    with (
        patch(
            "homeassistant.components.vlc_telnet.config_flow.Client.connect",
            side_effect=connect_side_effect,
        ),
        patch(
            "homeassistant.components.vlc_telnet.config_flow.Client.login",
            side_effect=login_side_effect,
        ),
        patch(
            "homeassistant.components.vlc_telnet.config_flow.Client.disconnect",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HASSIO},
            data=HassioServiceInfo(
                config={
                    "password": "test-password",
                    "host": "1.1.1.1",
                    "port": 8888,
                    "name": "custom name",
                    "addon": "VLC",
                },
                name="VLC",
                slug="vlc",
                uuid="1234",
            ),
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == error
