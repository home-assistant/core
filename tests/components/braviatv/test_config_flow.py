"""Define tests for the Bravia TV config flow."""

from unittest.mock import ANY, AsyncMock

from pybravia import (
    BraviaAuthError,
    BraviaConnectionError,
    BraviaError,
    BraviaNotSupported,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.braviatv.const import (
    CONF_NICKNAME,
    CONF_USE_PSK,
    CONF_USE_SSL,
    DOMAIN,
    NICKNAME_PREFIX,
)
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER, ConfigEntryDisabler
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import instance_id
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .conftest import BRAVIA_SYSTEM_INFO

BRAVIA_SSDP = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location="http://bravia-host:52323/dmr.xml",
    upnp={
        ATTR_UPNP_UDN: "uuid:1234",
        ATTR_UPNP_FRIENDLY_NAME: "Living TV",
        ATTR_UPNP_MODEL_NAME: "KE-55XH9096",
        "X_ScalarWebAPI_DeviceInfo": {
            "X_ScalarWebAPI_ServiceList": {
                "X_ScalarWebAPI_ServiceType": [
                    "guide",
                    "system",
                    "audio",
                    "avContent",
                    "videoScreen",
                ],
            },
        },
    },
)

FAKE_BRAVIA_SSDP = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location="http://soundbar-host:52323/dmr.xml",
    upnp={
        ATTR_UPNP_UDN: "uuid:1234",
        ATTR_UPNP_FRIENDLY_NAME: "Sony Audio Device",
        ATTR_UPNP_MODEL_NAME: "HT-S700RF",
        "X_ScalarWebAPI_DeviceInfo": {
            "X_ScalarWebAPI_ServiceList": {
                "X_ScalarWebAPI_ServiceType": ["guide", "system", "audio", "avContent"],
            },
        },
    },
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_braviatv_client")


async def test_ssdp_discovery(
    hass: HomeAssistant, mock_braviatv_client: AsyncMock
) -> None:
    """Test that the device is discovered."""
    uuid = await instance_id.async_get(hass)
    nickname = f"{NICKNAME_PREFIX} {uuid[:6]}"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=BRAVIA_SSDP,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authorize"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_PSK: False, CONF_USE_SSL: False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pin"
    mock_braviatv_client.pair.assert_called_once_with(uuid, nickname)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: "1234"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "very_unique_string"
    assert result["title"] == "BRAVIA TV-Model"
    assert result["data"] == {
        CONF_HOST: "bravia-host",
        CONF_PIN: "1234",
        CONF_USE_PSK: False,
        CONF_USE_SSL: False,
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
        CONF_CLIENT_ID: uuid,
        CONF_NICKNAME: nickname,
    }
    mock_braviatv_client.connect.assert_called_once_with(
        pin="1234", clientid=uuid, nickname=nickname
    )
    mock_braviatv_client.set_wol_mode.assert_called_once_with(True)


async def test_ssdp_discovery_fake(hass: HomeAssistant) -> None:
    """Test that not Bravia device is not discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=FAKE_BRAVIA_SSDP,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_bravia_device"


async def test_ssdp_discovery_exist(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the existed device is not discovered."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=BRAVIA_SSDP,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_invalid_host(hass: HomeAssistant) -> None:
    """Test that errors are shown when the host is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "invalid/host"}
    )

    assert result["errors"] == {CONF_HOST: "invalid_host"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "bravia-host"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_PSK: False, CONF_USE_SSL: False}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: "1234"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("use_psk", "pin", "pair_calls"), [(False, "1234", 2), (True, "mypsk", 0)]
)
@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [
        (BraviaAuthError, "invalid_auth"),
        (BraviaNotSupported, "unsupported_model"),
        (BraviaConnectionError, "cannot_connect"),
    ],
)
async def test_form_error(
    hass: HomeAssistant,
    mock_braviatv_client: AsyncMock,
    use_psk: bool,
    pin: str,
    pair_calls: int,
    side_effect: type[Exception],
    error_message: str,
) -> None:
    """Test that PIN and PSK form errors are correct."""
    mock_braviatv_client.connect.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "bravia-host"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_PSK: use_psk}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: pin}
    )

    assert result["errors"] == {"base": error_message}
    assert mock_braviatv_client.pair.call_count == pair_calls

    mock_braviatv_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: pin}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PIN] == pin
    assert mock_braviatv_client.connect.call_count == 2


async def test_no_ip_control(
    hass: HomeAssistant, mock_braviatv_client: AsyncMock
) -> None:
    """Test that error are shown when IP Control is disabled on the TV."""
    mock_braviatv_client.pair.side_effect = BraviaError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "bravia-host"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_PSK: False}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_ip_control"


async def test_duplicate_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that error are shown when duplicates are added."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "bravia-host"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_PSK: False}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: "1234"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("use_ssl", [True, False])
async def test_create_entry_psk(
    hass: HomeAssistant,
    mock_braviatv: AsyncMock,
    mock_braviatv_client: AsyncMock,
    use_ssl: bool,
) -> None:
    """Test that entry is added correctly with a PSK."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "bravia-host"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authorize"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_PSK: True, CONF_USE_SSL: use_ssl}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "psk"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: "secret"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "very_unique_string"
    assert result["title"] == "BRAVIA TV-Model"
    assert result["data"] == {
        CONF_HOST: "bravia-host",
        CONF_PIN: "secret",
        CONF_USE_PSK: True,
        CONF_USE_SSL: use_ssl,
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }
    mock_braviatv_client.pair.assert_not_called()
    mock_braviatv_client.connect.assert_called_once_with(psk="secret")
    mock_braviatv.assert_called_once_with(host="bravia-host", session=ANY, ssl=use_ssl)
    mock_braviatv_client.set_wol_mode.assert_called_once_with(True)


@pytest.mark.parametrize("use_ssl", [True, False])
async def test_create_entry_pin(
    hass: HomeAssistant,
    mock_braviatv: AsyncMock,
    mock_braviatv_client: AsyncMock,
    use_ssl: bool,
) -> None:
    """Test that entry is added correctly with a PIN."""
    uuid = await instance_id.async_get(hass)
    nickname = f"{NICKNAME_PREFIX} {uuid[:6]}"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "bravia-host"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authorize"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_PSK: False, CONF_USE_SSL: use_ssl}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pin"
    mock_braviatv_client.pair.assert_called_once_with(uuid, nickname)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: "secret"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "very_unique_string"
    assert result["title"] == "BRAVIA TV-Model"
    assert result["data"] == {
        CONF_HOST: "bravia-host",
        CONF_PIN: "secret",
        CONF_USE_PSK: False,
        CONF_USE_SSL: use_ssl,
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
        CONF_CLIENT_ID: uuid,
        CONF_NICKNAME: nickname,
    }
    mock_braviatv_client.connect.assert_called_once_with(
        pin="secret", clientid=uuid, nickname=nickname
    )
    mock_braviatv.assert_called_once_with(host="bravia-host", session=ANY, ssl=use_ssl)
    mock_braviatv_client.set_wol_mode.assert_called_once_with(True)


async def test_reauth_successful_psk(
    hass: HomeAssistant,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test that the reauthorization of a legacy PIN entry with a PSK is successful."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="BRAVIA TV-Model",
        unique_id="very_unique_string",
        data={
            CONF_HOST: "bravia-host",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_PIN: "1234",
        },
    )
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authorize"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_PSK: True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: "newpsk"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data == {
        CONF_HOST: "bravia-host",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
        CONF_PIN: "newpsk",
        CONF_USE_PSK: True,
        CONF_USE_SSL: False,
    }
    mock_braviatv_client.connect.assert_called_once_with(psk="newpsk")
    mock_braviatv_client.set_wol_mode.assert_called_once_with(True)


async def test_reauth_successful_pin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test that the reauthorization with a PIN is successful."""
    uuid = await instance_id.async_get(hass)
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authorize"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_PSK: False}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: "7777"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "bravia-host",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
        CONF_PIN: "7777",
        CONF_USE_PSK: False,
        CONF_USE_SSL: False,
        CONF_CLIENT_ID: uuid,
        CONF_NICKNAME: f"{NICKNAME_PREFIX} {uuid[:6]}",
    }
    mock_braviatv_client.connect.assert_called_once_with(
        pin="7777", clientid=uuid, nickname=f"{NICKNAME_PREFIX} {uuid[:6]}"
    )
    mock_braviatv_client.set_wol_mode.assert_called_once_with(True)


@pytest.mark.parametrize("use_psk", [True, False])
@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [
        (BraviaAuthError, "invalid_auth"),
        (BraviaNotSupported, "unsupported_model"),
        (BraviaConnectionError, "cannot_connect"),
    ],
)
async def test_reauth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    use_psk: bool,
    side_effect: type[Exception],
    error_message: str,
) -> None:
    """Test that the reauthorization recovers from errors."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authorize"

    mock_braviatv_client.connect.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_PSK: use_psk, CONF_USE_SSL: False}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: "wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_message}

    mock_braviatv_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: "7777"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PIN] == "7777"


@pytest.mark.parametrize(
    (
        "existing_unique_id",
        "existing_mac",
        "disabled_by",
        "expected_type",
        "expected_unique_ids",
    ),
    [
        pytest.param(
            "",
            "11:22:33:44:55:66",
            None,
            FlowResultType.CREATE_ENTRY,
            ["11:22:33:44:55:66", "aa:bb:cc:dd:ee:ff"],
            id="other_tv_without_cid",
        ),
        pytest.param(
            "aa:bb:cc:dd:ee:ff",
            "AA:BB:CC:DD:EE:FF",
            None,
            FlowResultType.ABORT,
            ["aa:bb:cc:dd:ee:ff"],
            id="same_tv_migrated",
        ),
        pytest.param(
            "",
            "AA:BB:CC:DD:EE:FF",
            ConfigEntryDisabler.USER,
            FlowResultType.ABORT,
            [""],
            id="same_tv_disabled",
        ),
    ],
)
async def test_user_flow_with_empty_cid(
    hass: HomeAssistant,
    mock_braviatv_client: AsyncMock,
    existing_unique_id: str,
    existing_mac: str,
    disabled_by: ConfigEntryDisabler | None,
    expected_type: FlowResultType,
    expected_unique_ids: list[str],
) -> None:
    """Test a television that reports an empty CID is identified by its MAC."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=existing_unique_id,
        data={CONF_HOST: "other-host", CONF_MAC: existing_mac},
        disabled_by=disabled_by,
    ).add_to_hass(hass)
    mock_braviatv_client.get_system_info.return_value = {
        **BRAVIA_SYSTEM_INFO,
        "cid": "",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "bravia-host"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_USE_PSK: True, CONF_USE_SSL: False}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: "secret"}
    )

    assert result["type"] is expected_type
    assert (
        sorted(entry.unique_id for entry in hass.config_entries.async_entries(DOMAIN))
        == expected_unique_ids
    )
