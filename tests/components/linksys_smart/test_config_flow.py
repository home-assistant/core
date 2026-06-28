"""Test Linksys Smart Wi-Fi config flow."""

from unittest.mock import AsyncMock, patch

from jnap import GetDeviceInfoResponse, JNAPError, JNAPUnauthorizedError
import pytest

from homeassistant import config_entries
from homeassistant.components.linksys_smart import config_flow as linksys_config_flow
from homeassistant.components.linksys_smart.config_flow import LinksysConfigFlow
from homeassistant.components.linksys_smart.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from tests.common import MockConfigEntry

SSDP_HOST = "192.168.1.1"
SSDP_UDN = "ebf5a0a0-1dd1-11b2-a90f-d8ec5e4436ec"

MOCK_SSDP_DISCOVERY = SsdpServiceInfo(
    ssdp_usn=f"uuid:{SSDP_UDN}::urn:schemas-upnp-org:device:InternetGatewayDevice:2",
    ssdp_st="urn:schemas-upnp-org:device:InternetGatewayDevice:2",
    ssdp_location=f"http://{SSDP_HOST}:49153/IGDdevicedesc.xml",
    upnp={
        ATTR_UPNP_MANUFACTURER: "Linksys",
        ATTR_UPNP_FRIENDLY_NAME: "Linksys21541",
        ATTR_UPNP_UDN: f"uuid:{SSDP_UDN}",
    },
)

SERIAL = "38U10M37B21541"

_GOOD_CLIENT = {
    "get_device_info": AsyncMock(
        return_value=GetDeviceInfoResponse(
            description="Velop AX4200 WiFi 6 System", serial_number=SERIAL
        )
    ),
    "get_devices": AsyncMock(),
}


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Velop AX4200 WiFi 6 System"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.multiple(
        "jnap.JNAPClient",
        get_device_info=AsyncMock(),
        get_devices=AsyncMock(side_effect=JNAPUnauthorizedError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Velop AX4200 WiFi 6 System"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.multiple(
        "jnap.JNAPClient",
        get_device_info=AsyncMock(side_effect=JNAPError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Velop AX4200 WiFi 6 System"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect_on_get_devices_error(hass: HomeAssistant) -> None:
    """Test we handle JNAPError from get_devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.multiple(
        "jnap.JNAPClient",
        get_device_info=AsyncMock(
            return_value=GetDeviceInfoResponse(
                description="Velop AX4200 WiFi 6 System", serial_number=SERIAL
            )
        ),
        get_devices=AsyncMock(side_effect=JNAPError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error_on_get_devices_error(hass: HomeAssistant) -> None:
    """Test we surface unexpected errors from get_devices as unknown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch.object(linksys_config_flow._LOGGER, "exception") as mock_exception,
        patch.multiple(
            "jnap.JNAPClient",
            get_device_info=AsyncMock(
                return_value=GetDeviceInfoResponse(
                    description="Velop AX4200 WiFi 6 System", serial_number=SERIAL
                )
            ),
            get_devices=AsyncMock(side_effect=Exception),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    mock_exception.assert_called_once_with("Unexpected exception")


async def test_user_flow_aborts_already_configured(hass: HomeAssistant) -> None:
    """Test that the user flow aborts when the serial number matches an existing entry."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={CONF_HOST: "1.1.1.1", CONF_PASSWORD: "old-password"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_discovery(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test SSDP discovery shows confirm form then creates an entry on valid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DISCOVERY,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Velop AX4200 WiFi 6 System"
    assert result["data"][CONF_HOST] == SSDP_HOST
    assert result["data"][CONF_PASSWORD] == "test-password"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_aborts_not_linksys_device(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts for non-Linksys devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="uuid:other-device",
            ssdp_st="urn:schemas-upnp-org:device:InternetGatewayDevice:2",
            ssdp_location=f"http://{SSDP_HOST}:49153/device.xml",
            upnp={ATTR_UPNP_MANUFACTURER: "SomeOtherBrand"},
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_linksys_device"


async def test_ssdp_aborts_already_configured_via_serial(
    hass: HomeAssistant,
) -> None:
    """Test SSDP confirm aborts when a config entry with the same serial number already exists."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={CONF_HOST: SSDP_HOST, CONF_PASSWORD: "old-password"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DISCOVERY,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test-password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_aborts_missing_host(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when no host can be extracted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn=f"uuid:{SSDP_UDN}::urn:schemas-upnp-org:device:InternetGatewayDevice:2",
            ssdp_st="urn:schemas-upnp-org:device:InternetGatewayDevice:2",
            ssdp_location=None,
            upnp={
                ATTR_UPNP_MANUFACTURER: "Linksys",
                ATTR_UPNP_FRIENDLY_NAME: "Linksys21541",
                ATTR_UPNP_UDN: f"uuid:{SSDP_UDN}",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_aborts_matching_flow_already_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test SSDP discovery aborts when a matching flow is already running."""
    discovery_info = SsdpServiceInfo(
        ssdp_usn="uuid:other-device",
        ssdp_st="urn:schemas-upnp-org:device:InternetGatewayDevice:2",
        ssdp_location=f"http://{SSDP_HOST}:49153/IGDdevicedesc.xml",
        upnp={
            ATTR_UPNP_MANUFACTURER: "Linksys",
            ATTR_UPNP_FRIENDLY_NAME: "Linksys21541",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


def test_is_matching() -> None:
    """Test config flow matching uses the host."""
    flow = LinksysConfigFlow()
    flow._host = "192.168.1.1"

    matching_flow = LinksysConfigFlow()
    matching_flow._host = "192.168.1.1"

    non_matching_flow = LinksysConfigFlow()
    non_matching_flow._host = "10.0.0.1"

    no_host_flow = LinksysConfigFlow()

    assert flow.is_matching(matching_flow)
    assert not flow.is_matching(non_matching_flow)
    assert not flow.is_matching(no_host_flow)


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(
            {
                "get_device_info": AsyncMock(),
                "get_devices": AsyncMock(side_effect=JNAPUnauthorizedError),
            },
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            {"get_device_info": AsyncMock(side_effect=JNAPError)},
            "cannot_connect",
            id="cannot_connect",
        ),
    ],
)
async def test_ssdp_confirm_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: dict,
    expected_error: str,
) -> None:
    """Test error recovery in the SSDP confirm step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=MOCK_SSDP_DISCOVERY,
    )

    with patch.multiple("jnap.JNAPClient", **side_effect):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "wrong-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "correct-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(
            {
                "get_device_info": AsyncMock(),
                "get_devices": AsyncMock(side_effect=JNAPUnauthorizedError),
            },
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            {"get_device_info": AsyncMock(side_effect=JNAPError)},
            "cannot_connect",
            id="cannot_connect",
        ),
    ],
)
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: dict,
    expected_error: str,
) -> None:
    """Test the reauth flow shows errors then succeeds on valid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "old-password",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch.multiple("jnap.JNAPClient", **side_effect):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "admin", CONF_PASSWORD: "wrong-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    with patch.multiple("jnap.JNAPClient", **_GOOD_CLIENT):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "admin", CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"
