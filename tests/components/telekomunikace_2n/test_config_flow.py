"""Test the 2N Telekomunikace config flow."""
from datetime import datetime
from unittest.mock import patch

from py2n import Py2NDeviceData, Py2NDeviceSwitch
from py2n.exceptions import DeviceConnectionError, DeviceUnsupportedError
import pytest

from homeassistant.components.telekomunikace_2n.config_flow import (
    RESULT_CANNOT_CONNECT,
    RESULT_UNKNOWN,
    RESULT_UNSUPPORTED,
)
from homeassistant.components.telekomunikace_2n.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


class DeviceMock:
    """Mock for Py2NDevice."""

    def __init__(self):
        """Set up device mock."""
        self.data = MOCK_DEVICE_DATA
        self.initialized = True


MOCK_DEVICE_DATA = Py2NDeviceData(
    name="Test name",
    model="Test model",
    serial="00-0000-0000",
    host="1.1.1.1",
    mac="00-00-00-00-00-00",
    firmware="1.0.0.0.0",
    hardware="0v0",
    uptime=datetime.now,
    switches=[Py2NDeviceSwitch(id=1, active=False, locked=False)],
)

MOCK_CONFIG_DATA = {
    CONF_HOST: "10.0.0.1",
    CONF_USERNAME: "fake_user",
    CONF_PASSWORD: "fake_pass",
}


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_invalid_host(hass: HomeAssistant) -> None:
    """Test if invalid host error is handled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "10.0.0"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "invalid_host"}


@pytest.mark.parametrize(
    "mapping",
    [
        (DeviceConnectionError, RESULT_CANNOT_CONNECT),
        (DeviceUnsupportedError, RESULT_UNSUPPORTED),
        (Exception, RESULT_UNKNOWN),
    ],
)
async def test_connection_error(hass: HomeAssistant, mapping) -> None:
    """Test if errors are handled."""
    error, message = mapping

    with patch("py2n.Py2NDevice.create", side_effect=error):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "10.0.0.1"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": message}


# Check for DeviceApiError


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test if already configured error is handled."""
    unique_id = MOCK_DEVICE_DATA.mac

    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    with patch("py2n.Py2NDevice.create", return_value=DeviceMock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=MOCK_CONFIG_DATA
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_successful(hass: HomeAssistant):
    """Test starting a successful reauthentication flow."""

    unique_id = MOCK_DEVICE_DATA.mac
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    with patch("py2n.Py2NDevice.create", return_value=DeviceMock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "fake_user", CONF_PASSWORD: "fake_pass"},
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    "mapping",
    [
        (DeviceConnectionError, RESULT_CANNOT_CONNECT),
        (DeviceUnsupportedError, RESULT_UNSUPPORTED),
        (Exception, RESULT_UNKNOWN),
    ],
)
async def test_reauth_unsuccessful(hass: HomeAssistant, mapping):
    """Test starting a unsuccessful reauthentication flow."""
    error, message = mapping

    unique_id = MOCK_DEVICE_DATA.mac
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    with patch("py2n.Py2NDevice.create", side_effect=error):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "fake_user", CONF_PASSWORD: "fake_pass"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": message}
