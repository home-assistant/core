"""Tests for the Go2rtc config flow."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.go2rtc.const import CONF_BINARY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_single_instance_allowed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that flow will abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_docker_with_binary(
    hass: HomeAssistant,
) -> None:
    """Test config flow, where HA is running in docker with a go2rtc binary available."""
    binary = "/usr/bin/go2rtc"
    with (
        patch(
            "homeassistant.components.go2rtc.config_flow.is_docker_env",
            return_value=True,
        ),
        patch(
            "homeassistant.components.go2rtc.config_flow.shutil.which",
            return_value=binary,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "go2rtc"
        assert result["data"] == {
            CONF_BINARY: binary,
            CONF_HOST: "http://localhost:1984/",
        }


@pytest.mark.usefixtures("mock_setup_entry", "mock_client")
@pytest.mark.parametrize(
    ("is_docker_env", "shutil_which"),
    [
        (True, None),
        (False, None),
        (False, "/usr/bin/go2rtc"),
    ],
)
async def test_config_flow_host(
    hass: HomeAssistant,
    is_docker_env: bool,
    shutil_which: str | None,
) -> None:
    """Test config flow with host input."""
    with (
        patch(
            "homeassistant.components.go2rtc.config_flow.is_docker_env",
            return_value=is_docker_env,
        ),
        patch(
            "homeassistant.components.go2rtc.config_flow.shutil.which",
            return_value=shutil_which,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "host"
        host = "http://go2rtc.local:1984/"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: host},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "go2rtc"
        assert result["data"] == {
            CONF_HOST: host,
        }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_errors(
    hass: HomeAssistant,
    mock_client: Mock,
) -> None:
    """Test flow errors."""
    with (
        patch(
            "homeassistant.components.go2rtc.config_flow.is_docker_env",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "host"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "go2rtc.local:1984/"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"host": "invalid_url_schema"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "http://"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"host": "invalid_url"}

        host = "http://go2rtc.local:1984/"
        mock_client.streams.list.side_effect = Exception
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: host},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"host": "cannot_connect"}

        mock_client.streams.list.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: host},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "go2rtc"
        assert result["data"] == {
            CONF_HOST: host,
        }
