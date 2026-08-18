"""Test the VRChat API client helpers."""

from typing import Any, cast
from unittest.mock import Mock

import vrchatapi

from homeassistant.components.vrchat.api import (
    get_cookie_dict,
    make_cookie,
    set_cookie_dict,
)
from homeassistant.components.vrchat.const import (
    CONF_COOKIE_2FA,
    CONF_COOKIE_AUTH,
    VRCHAT_API_HOST,
)


def test_cookie_dict_omits_empty_cookies() -> None:
    """Test empty authentication cookies are neither copied nor restored."""
    api = cast(vrchatapi.ApiClient, Mock())
    cookie_jar = cast(Any, api.rest_client.cookie_jar)
    cookie_jar._cookies = {
        VRCHAT_API_HOST: {
            "/": {
                CONF_COOKIE_AUTH: make_cookie(CONF_COOKIE_AUTH, "auth-cookie"),
                CONF_COOKIE_2FA: make_cookie(CONF_COOKIE_2FA, ""),
            }
        }
    }

    cookie = get_cookie_dict(api)

    assert cookie == {CONF_COOKIE_AUTH: "auth-cookie"}

    set_cookie_dict(api, cookie)

    cookie_jar.set_cookie.assert_called_once()
    stored_cookie = cookie_jar.set_cookie.call_args.args[0]
    assert stored_cookie.name == CONF_COOKIE_AUTH
    assert stored_cookie.value == "auth-cookie"
