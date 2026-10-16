"""Test the nexia config flow."""

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import aiohttp
from nexia.const import BRAND_ASAIR, BRAND_NEXIA
from nexia.home import NexiaHome
import pytest

from homeassistant import config_entries
from homeassistant.components.nexia.const import CONF_BRAND, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_BRAND: BRAND_NEXIA,
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}


@contextmanager
def _patch_success() -> Generator[None]:
    """Patch a successful login and entry setup."""
    with (
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.get_name",
            return_value="myhouse",
        ),
        patch("homeassistant.components.nexia.config_flow.NexiaHome.login"),
        patch("homeassistant.components.nexia.async_setup_entry", return_value=True),
    ):
        yield


@pytest.mark.parametrize("brand", [BRAND_ASAIR, BRAND_NEXIA])
async def test_form(hass: HomeAssistant, brand) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.get_name",
            return_value="myhouse",
        ),
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.login",
            side_effect=MagicMock(),
        ),
        patch(
            "homeassistant.components.nexia.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BRAND: brand, CONF_USERNAME: "username", CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    # pylint: disable-next=home-assistant-tests-config-flow-unique-id
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "myhouse"
    assert result2["data"] == {
        CONF_BRAND: brand,
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.login",
        ),
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.get_name",
            return_value=None,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: BRAND_NEXIA,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.login",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: BRAND_NEXIA,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_invalid_auth_http_401(hass: HomeAssistant) -> None:
    """Test we handle invalid auth error from http 401."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.login",
        side_effect=aiohttp.ClientResponseError(
            status=401, request_info=MagicMock(), history=MagicMock()
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: BRAND_NEXIA,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect_not_found(hass: HomeAssistant) -> None:
    """Test we handle cannot connect from an http not found error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.login",
        side_effect=aiohttp.ClientResponseError(
            status=404, request_info=MagicMock(), history=MagicMock()
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: BRAND_NEXIA,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_broad_exception(hass: HomeAssistant) -> None:
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.login",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: BRAND_NEXIA,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY


REAUTH_ENTRY_DATA = {
    CONF_BRAND: BRAND_ASAIR,
    CONF_USERNAME: "username",
    CONF_PASSWORD: "old_password",
}


def _patch_login(house_id: int = 123, side_effect: Exception | None = None):
    """Patch NexiaHome.login to set the house ID or raise."""

    def _login(nexia_home: NexiaHome) -> None:
        if side_effect is not None:
            raise side_effect
        nexia_home.house_id = house_id

    return patch.object(NexiaHome, "login", autospec=True, side_effect=_login)


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth updates the password."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=REAUTH_ENTRY_DATA, unique_id="123", minor_version=2
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        _patch_login(),
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.get_name",
            return_value="myhouse",
        ),
        patch("homeassistant.components.nexia.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new_password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == REAUTH_ENTRY_DATA | {CONF_PASSWORD: "new_password"}


@pytest.mark.parametrize(
    ("side_effect", "name", "error"),
    [
        pytest.param(
            aiohttp.ClientResponseError(MagicMock(), (), status=401),
            "myhouse",
            "invalid_auth",
            id="invalid_auth_http_401",
        ),
        pytest.param(None, None, "invalid_auth", id="invalid_auth_no_name"),
        pytest.param(TimeoutError, "myhouse", "cannot_connect", id="cannot_connect"),
        pytest.param(ValueError, "myhouse", "unknown", id="unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    side_effect: Exception | type[Exception] | None,
    name: str | None,
    error: str,
) -> None:
    """Test reauth handles errors and can recover."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=REAUTH_ENTRY_DATA, unique_id="123", minor_version=2
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with (
        _patch_login(side_effect=side_effect),
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.get_name",
            return_value=name,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "wrong_password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    with (
        _patch_login(),
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.get_name",
            return_value="myhouse",
        ),
        patch("homeassistant.components.nexia.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new_password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new_password"


async def test_reauth_wrong_account(hass: HomeAssistant) -> None:
    """Test reauth aborts when the login belongs to another home."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=REAUTH_ENTRY_DATA, unique_id="123", minor_version=2
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with (
        _patch_login(house_id=456),
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.get_name",
            return_value="otherhouse",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new_password"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data[CONF_PASSWORD] == "old_password"
