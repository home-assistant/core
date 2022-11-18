"""Tests for the iCloud config flow."""
from unittest.mock import MagicMock, Mock, patch

from pyicloud.exceptions import PyiCloudFailedLoginException
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.icloud.config_flow import (
    CONF_TRUSTED_DEVICE,
    CONF_VERIFICATION_CODE,
)
from homeassistant.components.icloud.const import (
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    CONF_WITH_FAMILY,
    DEFAULT_GPS_ACCURACY_THRESHOLD,
    DEFAULT_MAX_INTERVAL,
    DEFAULT_WITH_FAMILY,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import (
    MOCK_CONFIG,
    PASSWORD,
    PASSWORD_2,
    TRUSTED_DEVICES,
    USERNAME,
    WITH_FAMILY,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="icloud_bypass_setup", autouse=True)
def icloud_bypass_setup_fixture():
    """Mock component setup."""
    with patch("homeassistant.components.icloud.async_setup_entry", return_value=True):
        yield


@pytest.fixture(name="service")
def mock_controller_service():
    """Mock a successful service."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=True)
        service_mock.return_value.validate_verification_code = Mock(return_value=True)
        yield service_mock


@pytest.fixture(name="service_2fa")
def mock_controller_2fa_service():
    """Mock a successful 2fa service."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = True
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.validate_2fa_code = Mock(return_value=True)
        service_mock.return_value.is_trusted_session = False
        yield service_mock


@pytest.fixture(name="service_authenticated")
def mock_controller_service_authenticated():
    """Mock a successful service while already authenticate."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = False
        service_mock.return_value.is_trusted_session = True
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=True)
        service_mock.return_value.validate_2fa_code = Mock(return_value=True)
        service_mock.return_value.validate_verification_code = Mock(return_value=True)
        yield service_mock


@pytest.fixture(name="service_authenticated_no_device")
def mock_controller_service_authenticated_no_device():
    """Mock a successful service while already authenticate, but without device."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = False
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=True)
        service_mock.return_value.validate_verification_code = Mock(return_value=True)
        service_mock.return_value.devices = {}
        yield service_mock


@pytest.fixture(name="service_authenticated_not_trusted")
def mock_controller_service_authenticated_not_trusted():
    """Mock a successful service while already authenticated, but the session is not trusted."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = False
        service_mock.return_value.is_trusted_session = False
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=True)
        service_mock.return_value.validate_2fa_code = Mock(return_value=True)
        service_mock.return_value.validate_verification_code = Mock(return_value=True)
        yield service_mock


@pytest.fixture(name="service_send_verification_code_failed")
def mock_controller_service_send_verification_code_failed():
    """Mock a failed service during sending verification code step."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=False)
        yield service_mock


@pytest.fixture(name="service_validate_2fa_code_failed")
def mock_controller_service_validate_2fa_code_failed():
    """Mock a failed service during validation of 2FA verification code step."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = True
        service_mock.return_value.validate_2fa_code = Mock(return_value=False)
        yield service_mock


@pytest.fixture(name="service_validate_verification_code_failed")
def mock_controller_service_validate_verification_code_failed():
    """Mock a failed service during validation of verification code step."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = False
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.trusted_devices = TRUSTED_DEVICES
        service_mock.return_value.send_verification_code = Mock(return_value=True)
        service_mock.return_value.validate_verification_code = Mock(return_value=False)
        yield service_mock


async def test_user(hass: HomeAssistant, service: MagicMock):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=None
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # test with required
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE


async def test_user_with_cookie(hass: HomeAssistant, service_authenticated: MagicMock):
    """Test user config with presence of a cookie."""
    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_WITH_FAMILY: WITH_FAMILY,
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USERNAME
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_WITH_FAMILY] == WITH_FAMILY
    assert result["data"][CONF_MAX_INTERVAL] == DEFAULT_MAX_INTERVAL
    assert result["data"][CONF_GPS_ACCURACY_THRESHOLD] == DEFAULT_GPS_ACCURACY_THRESHOLD


async def test_login_failed(hass: HomeAssistant):
    """Test when we have errors during login."""
    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService.authenticate",
        side_effect=PyiCloudFailedLoginException(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}


async def test_no_device(
    hass: HomeAssistant, service_authenticated_no_device: MagicMock
):
    """Test when we have no devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_device"


async def test_trusted_device(hass: HomeAssistant, service: MagicMock):
    """Test trusted_device step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE


async def test_trusted_device_success(hass: HomeAssistant, service: MagicMock):
    """Test trusted_device step success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TRUSTED_DEVICE: 0}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE


async def test_send_verification_code_failed(
    hass: HomeAssistant, service_send_verification_code_failed: MagicMock
):
    """Test when we have errors during send_verification_code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TRUSTED_DEVICE: 0}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {CONF_TRUSTED_DEVICE: "send_verification_code"}


async def test_verification_code(hass: HomeAssistant, service: MagicMock):
    """Test verification_code step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TRUSTED_DEVICE: 0}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE


async def test_verification_code_success(hass: HomeAssistant, service: MagicMock):
    """Test verification_code step success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TRUSTED_DEVICE: 0}
    )
    service.return_value.requires_2sa = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_VERIFICATION_CODE: "0"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USERNAME
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_WITH_FAMILY] == DEFAULT_WITH_FAMILY
    assert result["data"][CONF_MAX_INTERVAL] == DEFAULT_MAX_INTERVAL
    assert result["data"][CONF_GPS_ACCURACY_THRESHOLD] == DEFAULT_GPS_ACCURACY_THRESHOLD


async def test_validate_verification_code_failed(
    hass: HomeAssistant, service_validate_verification_code_failed: MagicMock
):
    """Test when we have errors during validate_verification_code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TRUSTED_DEVICE: 0}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_VERIFICATION_CODE: "0"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {"base": "validate_verification_code"}


async def test_2fa_code_success(hass: HomeAssistant, service_2fa: MagicMock):
    """Test 2fa step success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    service_2fa.return_value.requires_2fa = False
    service_2fa.return_value.requires_2sa = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_VERIFICATION_CODE: "0"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USERNAME
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_WITH_FAMILY] == DEFAULT_WITH_FAMILY
    assert result["data"][CONF_MAX_INTERVAL] == DEFAULT_MAX_INTERVAL
    assert result["data"][CONF_GPS_ACCURACY_THRESHOLD] == DEFAULT_GPS_ACCURACY_THRESHOLD


async def test_validate_2fa_code_failed(
    hass: HomeAssistant, service_validate_2fa_code_failed: MagicMock
):
    """Test when we have errors during validate_verification_code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_VERIFICATION_CODE: "0"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE
    assert result["errors"] == {"base": "validate_verification_code"}


async def test_password_update(hass: HomeAssistant, service_authenticated: MagicMock):
    """Test that password reauthentication works successfully."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "unique_id": config_entry.unique_id},
        data={**MOCK_CONFIG},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: PASSWORD_2}
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PASSWORD] == PASSWORD_2


async def test_password_update_wrong_password(hass: HomeAssistant):
    """Test that during password reauthentication wrong password returns correct error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "unique_id": config_entry.unique_id},
        data={**MOCK_CONFIG},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM

    with patch(
        "homeassistant.components.icloud.config_flow.PyiCloudService.authenticate",
        side_effect=PyiCloudFailedLoginException(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: PASSWORD_2}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}
