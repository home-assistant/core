"""Tests for Vodafone Station config flow."""

from unittest.mock import patch

from aiovodafone import exceptions as aiovodafone_exceptions
import pytest

from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.components.vodafone_station.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry


async def test_user(hass: HomeAssistant) -> None:
    """Test starting a flow by user."""
    with (
        patch(
            "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.login",
        ),
        patch(
            "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.logout",
        ),
        patch(
            "homeassistant.components.vodafone_station.async_setup_entry"
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_HOST] == "fake_host"
        assert result["data"][CONF_USERNAME] == "fake_username"
        assert result["data"][CONF_PASSWORD] == "fake_password"
        assert not result["result"].unique_id
        await hass.async_block_till_done()

    assert mock_setup_entry.called


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (aiovodafone_exceptions.CannotConnect, "cannot_connect"),
        (aiovodafone_exceptions.CannotAuthenticate, "invalid_auth"),
        (aiovodafone_exceptions.AlreadyLogged, "already_logged"),
        (aiovodafone_exceptions.ModelNotSupported, "model_not_supported"),
        (ConnectionResetError, "unknown"),
    ],
)
async def test_exception_connection(hass: HomeAssistant, side_effect, error) -> None:
    """Test starting a flow by user with a connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch(
        "aiovodafone.api.VodafoneStationSercommApi.login",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] is not None
        assert result["errors"]["base"] == error

        # Should be recoverable after hits error
        with (
            patch(
                "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.get_devices_data",
                return_value={
                    "wifi_user": "on|laptop|device-1|xx:xx:xx:xx:xx:xx|192.168.100.1||2.4G",
                    "ethernet": "laptop|device-2|yy:yy:yy:yy:yy:yy|192.168.100.2|;",
                },
            ),
            patch(
                "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.login",
            ),
            patch(
                "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.logout",
            ),
            patch(
                "homeassistant.components.vodafone_station.async_setup_entry",
            ),
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_HOST: "fake_host",
                    CONF_USERNAME: "fake_username",
                    CONF_PASSWORD: "fake_password",
                },
            )
            await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "fake_host"
        assert result2["data"] == {
            "host": "fake_host",
            "username": "fake_username",
            "password": "fake_password",
        }


async def test_reauth_successful(hass: HomeAssistant) -> None:
    """Test starting a reauthentication flow."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.login",
        ),
        patch(
            "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.logout",
        ),
        patch(
            "homeassistant.components.vodafone_station.async_setup_entry",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": mock_config.entry_id},
            data=mock_config.data,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PASSWORD: "other_fake_password",
            },
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (aiovodafone_exceptions.CannotConnect, "cannot_connect"),
        (aiovodafone_exceptions.CannotAuthenticate, "invalid_auth"),
        (aiovodafone_exceptions.AlreadyLogged, "already_logged"),
        (ConnectionResetError, "unknown"),
    ],
)
async def test_reauth_not_successful(hass: HomeAssistant, side_effect, error) -> None:
    """Test starting a reauthentication flow but no connection found."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.login",
            side_effect=side_effect,
        ),
        patch(
            "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.logout",
        ),
        patch(
            "homeassistant.components.vodafone_station.async_setup_entry",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": mock_config.entry_id},
            data=mock_config.data,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PASSWORD: "other_fake_password",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] is not None
        assert result["errors"]["base"] == error

        # Should be recoverable after hits error
        with (
            patch(
                "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.get_devices_data",
                return_value={
                    "wifi_user": "on|laptop|device-1|xx:xx:xx:xx:xx:xx|192.168.100.1||2.4G",
                    "ethernet": "laptop|device-2|yy:yy:yy:yy:yy:yy|192.168.100.2|;",
                },
            ),
            patch(
                "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.login",
            ),
            patch(
                "homeassistant.components.vodafone_station.config_flow.VodafoneStationSercommApi.logout",
            ),
            patch(
                "homeassistant.components.vodafone_station.async_setup_entry",
            ),
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_PASSWORD: "fake_password",
                },
            )
            await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CONSIDER_HOME: 37,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_CONSIDER_HOME: 37,
    }
