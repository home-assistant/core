"""Test the Cookidoo config flow."""

from collections.abc import Callable
from dataclasses import asdict
from typing import Any
from unittest.mock import AsyncMock

from cookidoo_api import CookidooAuthData
from cookidoo_api.exceptions import (
    CookidooAuthException,
    CookidooException,
    CookidooParseException,
    CookidooRequestException,
)
import pytest

from homeassistant.components.cookidoo.const import CONF_UDN, DOMAIN
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_EMAIL,
    CONF_LANGUAGE,
    CONF_PASSWORD,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_DEVICE_TYPE,
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .conftest import AUTH_DATA, COUNTRY, EMAIL, LANGUAGE, PASSWORD
from .test_init import setup_integration

from tests.common import MockConfigEntry

MOCK_DATA_USER_STEP = {
    CONF_EMAIL: EMAIL,
    CONF_PASSWORD: PASSWORD,
    CONF_COUNTRY: COUNTRY,
}

MOCK_DATA_LANGUAGE_STEP = {
    CONF_LANGUAGE: LANGUAGE,
}

TEST_SSDP_UDN = "uuid:3432E6654473"

TEST_SSDP_SERVICE_INFO = SsdpServiceInfo(
    ssdp_usn=f"{TEST_SSDP_UDN}::urn:device:vorwerk:nwotdevice:1",
    ssdp_st="urn:device:vorwerk:nwotdevice:1",
    ssdp_udn=TEST_SSDP_UDN,
    ssdp_location="http://192.0.2.7:49152/description.xml",
    upnp={
        ATTR_UPNP_DEVICE_TYPE: "urn:device:vorwerk:nwotdevice:1",
        ATTR_UPNP_SERIAL: "25145556024103937",
        ATTR_UPNP_UDN: TEST_SSDP_UDN,
    },
)

TEST_SSDP_UDN_2 = "uuid:112233445566"

TEST_SSDP_SERVICE_INFO_2 = SsdpServiceInfo(
    ssdp_usn=f"{TEST_SSDP_UDN_2}::urn:device:vorwerk:nwotdevice:1",
    ssdp_st="urn:device:vorwerk:nwotdevice:1",
    ssdp_udn=TEST_SSDP_UDN_2,
    ssdp_location="http://192.0.2.8:49152/description.xml",
    upnp={
        ATTR_UPNP_DEVICE_TYPE: "urn:device:vorwerk:nwotdevice:1",
        ATTR_UPNP_SERIAL: "25145556024103938",
        ATTR_UPNP_UDN: TEST_SSDP_UDN_2,
    },
)

MOCK_TOKEN = asdict(AUTH_DATA)
ROTATED_AUTH_DATA = CookidooAuthData(
    access_token="rotated-access-token",
    refresh_token="rotated-refresh-token",
    expires_at=1763000000.0,
)


@pytest.mark.parametrize(
    ("login_tokens", "rotated_tokens", "expected_token"),
    [
        pytest.param(AUTH_DATA, None, MOCK_TOKEN, id="tokens_from_the_login"),
        pytest.param(
            AUTH_DATA,
            ROTATED_AUTH_DATA,
            asdict(ROTATED_AUTH_DATA),
            id="tokens_rotated_during_validation",
        ),
        pytest.param(None, None, {}, id="no_tokens_from_the_login"),
    ],
)
async def test_flow_user_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    arrange_validation_tokens: Callable[
        [CookidooAuthData | None, CookidooAuthData | None], None
    ],
    login_tokens: CookidooAuthData | None,
    rotated_tokens: CookidooAuthData | None,
    expected_token: dict[str, Any],
) -> None:
    """Test we get the user flow and create entry with success.

    The entry is created with whatever tokens the validation ended up holding:
    the ones the login handed over, the ones a later request rotated them into,
    or none at all.
    """
    arrange_validation_tokens(login_tokens, rotated_tokens)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["handler"] == "cookidoo"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "language"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LANGUAGE_STEP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cookidoo"
    assert result["data"] == {
        **MOCK_DATA_USER_STEP,
        **MOCK_DATA_LANGUAGE_STEP,
        CONF_TOKEN: expected_token,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_reauth_drops_tokens_of_a_failed_attempt(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test a retried reauth does not persist the tokens of an earlier attempt.

    The first attempt logs in -- which hands us its tokens -- and only then
    fails, and the retry logs in without any. Those tokens belong to the
    credentials that were rejected, so they must not reach the entry.
    """
    await setup_integration(hass, cookidoo_config_entry)
    mock_cookidoo_client.reset_mock()

    result = await cookidoo_config_entry.start_reauth_flow(hass)

    user_info = mock_cookidoo_client.get_user_info.return_value
    mock_cookidoo_client.get_user_info.side_effect = [
        CookidooRequestException(),
        user_info,
    ]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "wrong-email", CONF_PASSWORD: "wrong-password"},
    )
    assert result["errors"] == {"base": "cannot_connect"}

    # The retried login yields no tokens, so nothing overwrites the stale pair
    mock_cookidoo_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "new-email", CONF_PASSWORD: "new-password"},
    )

    assert result["reason"] == "reauth_successful"
    assert cookidoo_config_entry.data[CONF_TOKEN] == {}


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CookidooRequestException(), "cannot_connect"),
        (CookidooParseException(), "cannot_connect"),
        (CookidooAuthException(), "invalid_auth"),
        (CookidooException(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_user_init_data_unknown_error_and_recover_on_step_1(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    login_success: Callable[[], None],
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test unknown errors."""
    mock_cookidoo_client.login.side_effect = raise_error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == text_error

    # Recover
    mock_cookidoo_client.login.side_effect = login_success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "language"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LANGUAGE_STEP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == "Cookidoo"

    assert result["data"] == {
        **MOCK_DATA_USER_STEP,
        **MOCK_DATA_LANGUAGE_STEP,
        CONF_TOKEN: MOCK_TOKEN,
    }


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CookidooRequestException(), "cannot_connect"),
        (CookidooParseException(), "cannot_connect"),
        (CookidooAuthException(), "invalid_auth"),
        (CookidooException(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_user_init_data_unknown_error_and_recover_on_step_2(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test unknown errors."""
    mock_cookidoo_client.get_additional_items.side_effect = raise_error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "language"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LANGUAGE_STEP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == text_error

    # Recover
    mock_cookidoo_client.get_additional_items.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LANGUAGE_STEP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == "Cookidoo"

    assert result["data"] == {
        **MOCK_DATA_USER_STEP,
        **MOCK_DATA_LANGUAGE_STEP,
        CONF_TOKEN: MOCK_TOKEN,
    }


async def test_flow_user_init_data_already_configured(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test we abort user data set when entry is already configured."""

    cookidoo_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_reconfigure_success(
    hass: HomeAssistant,
    cookidoo_config_entry: AsyncMock,
    mock_cookidoo_client: AsyncMock,
) -> None:
    """Test we get the reconfigure flow and create entry with success."""
    cookidoo_config_entry.add_to_hass(hass)
    await setup_integration(hass, cookidoo_config_entry)

    result = await cookidoo_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["handler"] == "cookidoo"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            **MOCK_DATA_USER_STEP,
            CONF_EMAIL: "new-email",
            CONF_PASSWORD: "new-password",
            CONF_COUNTRY: "DE",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "language"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LANGUAGE: "de-DE"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert cookidoo_config_entry.data == {
        **MOCK_DATA_USER_STEP,
        CONF_EMAIL: "new-email",
        CONF_PASSWORD: "new-password",
        CONF_COUNTRY: "DE",
        CONF_LANGUAGE: "de-DE",
        CONF_TOKEN: MOCK_TOKEN,
    }
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CookidooRequestException(), "cannot_connect"),
        (CookidooParseException(), "cannot_connect"),
        (CookidooException(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_reconfigure_init_data_unknown_error_and_recover_on_step_1(
    hass: HomeAssistant,
    cookidoo_config_entry: AsyncMock,
    mock_cookidoo_client: AsyncMock,
    login_success: Callable[[], None],
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test unknown errors."""
    mock_cookidoo_client.login.side_effect = raise_error

    cookidoo_config_entry.add_to_hass(hass)
    await setup_integration(hass, cookidoo_config_entry)

    result = await cookidoo_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["handler"] == "cookidoo"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**MOCK_DATA_USER_STEP, CONF_COUNTRY: "DE"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == text_error

    # Recover
    mock_cookidoo_client.login.side_effect = login_success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**MOCK_DATA_USER_STEP, CONF_COUNTRY: "DE"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "language"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LANGUAGE: "de-DE"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert cookidoo_config_entry.data == {
        **MOCK_DATA_USER_STEP,
        CONF_COUNTRY: "DE",
        CONF_LANGUAGE: "de-DE",
        CONF_TOKEN: MOCK_TOKEN,
    }
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CookidooRequestException(), "cannot_connect"),
        (CookidooParseException(), "cannot_connect"),
        (CookidooException(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_reconfigure_init_data_unknown_error_and_recover_on_step_2(
    hass: HomeAssistant,
    cookidoo_config_entry: AsyncMock,
    mock_cookidoo_client: AsyncMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test unknown errors."""
    mock_cookidoo_client.get_additional_items.side_effect = raise_error

    cookidoo_config_entry.add_to_hass(hass)
    await setup_integration(hass, cookidoo_config_entry)

    result = await cookidoo_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["handler"] == "cookidoo"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**MOCK_DATA_USER_STEP, CONF_COUNTRY: "DE"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "language"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LANGUAGE: "de-DE"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == text_error

    # Recover
    mock_cookidoo_client.get_additional_items.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LANGUAGE: "de-DE"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert cookidoo_config_entry.data == {
        **MOCK_DATA_USER_STEP,
        CONF_COUNTRY: "DE",
        CONF_LANGUAGE: "de-DE",
        CONF_TOKEN: MOCK_TOKEN,
    }
    assert len(hass.config_entries.async_entries()) == 1


async def test_flow_reconfigure_id_mismatch(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test we abort when the new config is not for the same user."""

    cookidoo_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        cookidoo_config_entry, unique_id="some_other_uuid"
    )

    result = await cookidoo_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **MOCK_DATA_USER_STEP,
            CONF_EMAIL: "new-email",
            CONF_PASSWORD: "new-password",
            CONF_COUNTRY: "DE",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


async def test_flow_reauth(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""

    cookidoo_config_entry.add_to_hass(hass)

    result = await cookidoo_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "new-email", CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert cookidoo_config_entry.data == {
        CONF_EMAIL: "new-email",
        CONF_PASSWORD: "new-password",
        CONF_COUNTRY: COUNTRY,
        CONF_LANGUAGE: LANGUAGE,
        CONF_TOKEN: MOCK_TOKEN,
    }
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CookidooRequestException(), "cannot_connect"),
        (CookidooParseException(), "cannot_connect"),
        (CookidooAuthException(), "invalid_auth"),
        (CookidooException(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_reauth_error_and_recover(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    cookidoo_config_entry: MockConfigEntry,
    login_success: Callable[[], None],
    raise_error,
    text_error,
) -> None:
    """Test reauth flow."""

    cookidoo_config_entry.add_to_hass(hass)

    result = await cookidoo_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_cookidoo_client.login.side_effect = raise_error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "new-email", CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    mock_cookidoo_client.login.side_effect = login_success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "new-email", CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert cookidoo_config_entry.data == {
        CONF_EMAIL: "new-email",
        CONF_PASSWORD: "new-password",
        CONF_COUNTRY: COUNTRY,
        CONF_LANGUAGE: LANGUAGE,
        CONF_TOKEN: MOCK_TOKEN,
    }
    assert len(hass.config_entries.async_entries()) == 1


async def test_flow_reauth_id_mismatch(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test we abort when the new auth is not for the same user."""

    cookidoo_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        cookidoo_config_entry, unique_id="some_other_uuid"
    )

    result = await cookidoo_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "new-email", CONF_PASSWORD: PASSWORD},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


async def test_flow_ssdp_discovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_cookidoo_client: AsyncMock
) -> None:
    """Test the Thermomix is discovered via SSDP and the flow completes."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=TEST_SSDP_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "language"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LANGUAGE_STEP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cookidoo"
    assert result["data"] == {
        **MOCK_DATA_USER_STEP,
        **MOCK_DATA_LANGUAGE_STEP,
        CONF_TOKEN: MOCK_TOKEN,
        CONF_UDN: [TEST_SSDP_UDN],
    }
    assert result["result"].unique_id == "sub_uuid"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_ssdp_discovery_device_already_configured(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test SSDP discovery aborts when this Thermomix was already set up.

    A completed entry is keyed by the account UUID and stores the device UDN in
    its data, so rediscovery must be deduplicated against that stored UDN.
    """
    cookidoo_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        cookidoo_config_entry,
        data={**cookidoo_config_entry.data, CONF_UDN: [TEST_SSDP_UDN]},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=TEST_SSDP_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_ssdp_discovery_account_already_configured(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test SSDP discovery aborts when the Cookidoo account is already set up."""
    cookidoo_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=TEST_SSDP_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # The discovered UDN is recorded on the existing account entry so later
    # announcements are deduplicated in the SSDP step.
    assert cookidoo_config_entry.data[CONF_UDN] == [TEST_SSDP_UDN]


async def test_flow_ssdp_discovery_second_device_same_account(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test a second Thermomix on an already-configured account is tracked.

    The account entry stores a collection of device UDNs, so discovering
    another device appends its UDN instead of overwriting; both devices are
    then deduplicated on later announcements.
    """
    cookidoo_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        cookidoo_config_entry,
        data={**cookidoo_config_entry.data, CONF_UDN: [TEST_SSDP_UDN_2]},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=TEST_SSDP_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Both devices are tracked on the single account entry.
    assert set(cookidoo_config_entry.data[CONF_UDN]) == {
        TEST_SSDP_UDN,
        TEST_SSDP_UDN_2,
    }

    # A later announcement from the pre-existing device is deduplicated in the
    # SSDP step.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=TEST_SSDP_SERVICE_INFO_2,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
