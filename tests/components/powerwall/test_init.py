"""Tests for the PowerwallDataManager."""

import datetime
from http.cookies import Morsel
from unittest.mock import MagicMock, patch

from aiohttp import CookieJar
from tesla_powerwall import AccessDeniedError, LoginResponse

from homeassistant.components.powerwall.const import (
    AUTH_COOKIE_KEY,
    CONFIG_ENTRY_COOKIE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .mocks import MOCK_GATEWAY_DIN, _mock_powerwall_with_fixtures

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_update_data_reauthenticate_on_access_denied(hass: HomeAssistant) -> None:
    """Test if _update_data of PowerwallDataManager reauthenticates on AccessDeniedError."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)
    # login responses for the different tests:
    # 1. login success on entry setup
    # 2. login success after reauthentication
    # 3. login failure after reauthentication
    mock_powerwall.login.return_value = LoginResponse.from_dict(
        {
            "firstname": "firstname",
            "lastname": "lastname",
            "token": "token",
            "roles": [],
            "loginTime": "loginTime",
        }
    )
    mock_powerwall.get_charge.return_value = 90.0
    mock_powerwall.is_authenticated.return_value = True

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_PASSWORD: "password",
        },
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.powerwall.config_flow.Powerwall",
            return_value=mock_powerwall,
        ),
        patch(
            "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        mock_powerwall.login.reset_mock(return_value=True)
        mock_powerwall.get_charge.side_effect = [AccessDeniedError("test"), 90.0]

        async_fire_time_changed(hass, utcnow() + datetime.timedelta(minutes=1))
        await hass.async_block_till_done()
        flows = hass.config_entries.flow.async_progress(DOMAIN)
        assert len(flows) == 0

        mock_powerwall.login.reset_mock()
        mock_powerwall.login.side_effect = AccessDeniedError("test")
        mock_powerwall.get_charge.side_effect = [AccessDeniedError("test"), 90.0]

        async_fire_time_changed(hass, utcnow() + datetime.timedelta(minutes=1))
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        flows = hass.config_entries.flow.async_progress(DOMAIN)
        assert len(flows) == 1
        reauth_flow = flows[0]
        assert reauth_flow["context"]["source"] == "reauth"


async def test_init_uses_cookie_if_present(hass: HomeAssistant) -> None:
    """Tests if the init will use the auth cookie if present.

    If the cookie is present, the login step will be skipped and info will be fetched directly (see _login_and_fetch_base_info).
    """
    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_PASSWORD: "somepassword",
            CONFIG_ENTRY_COOKIE: "somecookie",
        },
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.powerwall.config_flow.Powerwall",
            return_value=mock_powerwall,
        ),
        patch(
            "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert not mock_powerwall.login.called
        assert mock_powerwall.get_gateway_din.called


async def test_init_uses_password_if_no_cookies(hass: HomeAssistant) -> None:
    """Tests if the init will use the password if no auth cookie present."""
    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_PASSWORD: "somepassword",
        },
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.powerwall.config_flow.Powerwall",
            return_value=mock_powerwall,
        ),
        patch(
            "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        mock_powerwall.login.assert_called_with("somepassword")
        assert mock_powerwall.get_charge.called


async def test_init_saves_the_cookie(hass: HomeAssistant) -> None:
    """Tests that the cookie is properly saved."""
    mock_powerwall = await _mock_powerwall_with_fixtures(hass)
    mock_jar = MagicMock(CookieJar)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_PASSWORD: "somepassword",
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.powerwall.config_flow.Powerwall",
            return_value=mock_powerwall,
        ),
        patch(
            "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
        ),
        patch("homeassistant.components.powerwall.CookieJar", return_value=mock_jar),
    ):
        auth_cookie = Morsel()
        auth_cookie.set(AUTH_COOKIE_KEY, "somecookie", "somecookie")
        mock_jar.__iter__.return_value = [auth_cookie]

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.data[CONFIG_ENTRY_COOKIE] == "somecookie"


async def test_retry_ignores_cookie(hass: HomeAssistant) -> None:
    """Tests that retrying uses the password instead."""
    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_PASSWORD: "somepassword",
            CONFIG_ENTRY_COOKIE: "somecookie",
        },
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.powerwall.config_flow.Powerwall",
            return_value=mock_powerwall,
        ),
        patch(
            "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert not mock_powerwall.login.called
        assert mock_powerwall.get_gateway_din.called

        mock_powerwall.login.reset_mock()
        mock_powerwall.get_charge.reset_mock()

        mock_powerwall.get_charge.side_effect = [AccessDeniedError("test"), 90.0]

        async_fire_time_changed(hass, utcnow() + datetime.timedelta(minutes=1))
        await hass.async_block_till_done()

        mock_powerwall.login.assert_called_with("somepassword")
        assert mock_powerwall.get_charge.call_count == 2


async def test_reauth_ignores_and_clears_cookie(hass: HomeAssistant) -> None:
    """Tests that the reauth flow uses password and clears the cookie."""
    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_PASSWORD: "somepassword",
            CONFIG_ENTRY_COOKIE: "somecookie",
        },
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.powerwall.config_flow.Powerwall",
            return_value=mock_powerwall,
        ),
        patch(
            "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        mock_powerwall.login.reset_mock()
        mock_powerwall.get_charge.reset_mock()

        mock_powerwall.get_charge.side_effect = [
            AccessDeniedError("test"),
            AccessDeniedError("test"),
        ]

        async_fire_time_changed(hass, utcnow() + datetime.timedelta(minutes=1))
        await hass.async_block_till_done()

        mock_powerwall.login.assert_called_with("somepassword")
        assert mock_powerwall.get_charge.call_count == 2

        flows = hass.config_entries.flow.async_progress(DOMAIN)
        assert len(flows) == 1
        reauth_flow = flows[0]
        assert reauth_flow["context"]["source"] == "reauth"

        mock_powerwall.login.reset_mock()
        assert config_entry.data[CONFIG_ENTRY_COOKIE] is not None

        await hass.config_entries.flow.async_configure(
            reauth_flow["flow_id"], {CONF_PASSWORD: "somepassword"}
        )

        mock_powerwall.login.assert_called_with("somepassword")
        assert config_entry.data[CONFIG_ENTRY_COOKIE] is None


async def test_init_retries_with_password(hass: HomeAssistant) -> None:
    """Tests that the init retries with password if cookie fails."""
    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_PASSWORD: "somepassword",
            CONFIG_ENTRY_COOKIE: "somecookie",
        },
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.powerwall.config_flow.Powerwall",
            return_value=mock_powerwall,
        ),
        patch(
            "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
        ),
    ):
        mock_powerwall.get_gateway_din.side_effect = [
            AccessDeniedError("get_gateway_din"),
            MOCK_GATEWAY_DIN,
        ]

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        mock_powerwall.login.assert_called_with("somepassword")
        assert mock_powerwall.get_gateway_din.call_count == 2
