"""Define tests for the Dune HD config flow."""

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from homeassistant.components.dunehd.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG_HOSTNAME = {CONF_HOST: "dunehd-host"}
CONFIG_IP = {CONF_HOST: "10.10.10.12"}

DUNEHD_STATE = {"protocol_version": "4", "player_state": "navigator"}


@contextmanager
def _patch_success() -> Generator[None]:
    """Patch the Dune HD player to respond and skip entry setup."""
    with (
        patch("homeassistant.components.dunehd.async_setup_entry"),
        patch("pdunehd.DuneHDPlayer.update_state", return_value=DUNEHD_STATE),
    ):
        yield


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("invalid/host", id="slash"),
        pytest.param("example.com\n", id="trailing-newline"),
        pytest.param("example\n.com", id="newline-before-label-separator"),
        pytest.param("example.com\n.", id="newline-before-root-label"),
        pytest.param("local\n", id="single-label-newline"),
    ],
)
async def test_user_invalid_host(hass: HomeAssistant, host: str) -> None:
    """Test that errors are shown when the host is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("pdunehd.DuneHDPlayer.update_state", return_value={}) as mock_update:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: host},
        )

    mock_update.assert_not_called()

    assert result["errors"] == {CONF_HOST: "invalid_host"}

    with _patch_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_HOSTNAME,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("last_label_length", [62, 63])
@pytest.mark.parametrize("trailing_dot", ["", "."], ids=["no-root-dot", "root-dot"])
async def test_user_very_long_host(
    hass: HomeAssistant, last_label_length: int, trailing_dot: str
) -> None:
    """Test that errors are shown when the host is longer than 253 chars."""
    long_host = ".".join(["a" * 63] * 3 + ["b" * last_label_length]) + trailing_dot
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("pdunehd.DuneHDPlayer.update_state", return_value={}) as mock_update:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: long_host},
        )

    mock_update.assert_not_called()

    assert result["errors"] == {CONF_HOST: "invalid_host"}

    with _patch_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_HOSTNAME,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test that errors are shown when cannot connect to the host."""
    with patch("pdunehd.DuneHDPlayer.update_state", return_value={}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_IP,
        )

        assert result["errors"] == {CONF_HOST: "cannot_connect"}

    with _patch_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_IP,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when duplicates are added."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_HOSTNAME,
        title="dunehd-host",
    )
    config_entry.add_to_hass(hass)

    with patch("pdunehd.DuneHDPlayer.update_state", return_value=DUNEHD_STATE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_HOSTNAME,
        )

        assert result["errors"] == {CONF_HOST: "already_configured"}

    with _patch_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG_IP,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("dunehd-host", id="single-label"),
        pytest.param(".".join(["a" * 63] * 3 + ["b" * 61]), id="maximum-length"),
        pytest.param(
            ".".join(["a" * 63] * 3 + ["b" * 61]) + ".", id="maximum-length-root-dot"
        ),
    ],
)
async def test_create_entry(hass: HomeAssistant, host: str) -> None:
    """Test that the user step works."""
    with (
        patch("homeassistant.components.dunehd.async_setup_entry"),
        patch("pdunehd.DuneHDPlayer.update_state", return_value=DUNEHD_STATE),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: host},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == host
        assert result["data"] == {CONF_HOST: host}


async def test_create_entry_with_ipv6_address(hass: HomeAssistant) -> None:
    """Test that the user step works with device IPv6 address.."""
    with (
        patch("homeassistant.components.dunehd.async_setup_entry"),
        patch("pdunehd.DuneHDPlayer.update_state", return_value=DUNEHD_STATE),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "2001:db8::1428:57ab"},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "2001:db8::1428:57ab"
        assert result["data"] == {CONF_HOST: "2001:db8::1428:57ab"}
