"""Tests for the EARN-E P1 Meter config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from earn_e_p1 import EarnEP1Device, PacketType
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.earn_e_p1.const import CONF_SERIAL
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.discovery_flow import DiscoveryKey
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import (
    DHCP_DISCOVERY,
    DOMAIN,
    MOCK_EQUIPMENT_ID,
    MOCK_HOST,
    MOCK_HOST_2,
    MOCK_HOSTNAME,
    MOCK_MAC,
    MOCK_NEW_HOST,
    MOCK_NEW_MAC,
    MOCK_NEW_SERIAL,
    MOCK_SERIAL,
    MOCK_SERIAL_2,
)

DISCOVER_PATH = "homeassistant.components.earn_e_p1.config_flow.discover"
VALIDATE_PATH = "homeassistant.components.earn_e_p1.config_flow.validate"


def _mock_device(
    host: str = MOCK_HOST,
    serial: str | None = MOCK_SERIAL,
    equipment_id: str | None = MOCK_EQUIPMENT_ID,
    seen_packet_types: frozenset[PacketType] = frozenset(PacketType),
) -> EarnEP1Device:
    """Create a mock EarnEP1Device, validated unless told otherwise."""
    return EarnEP1Device(
        host=host,
        serial=serial,
        equipment_id=equipment_id,
        seen_packet_types=set(seen_packet_types),
    )


DISCOVERED_WITHOUT_TELEGRAM = [
    pytest.param(
        _mock_device(serial=None, equipment_id=None, seen_packet_types=frozenset()),
        id="no_serial",
    ),
    pytest.param(
        _mock_device(
            equipment_id=None, seen_packet_types=frozenset({PacketType.REALTIME})
        ),
        id="realtime_only",
    ),
]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_discovery_succeeds(hass: HomeAssistant) -> None:
    """Test user flow when auto-discovery finds a device with serial."""
    with patch(DISCOVER_PATH, return_value=[_mock_device()]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"EARN-E P1 ({MOCK_HOST})"
    assert result["data"] == {CONF_HOST: MOCK_HOST, CONF_SERIAL: MOCK_SERIAL}
    assert result["result"].unique_id == MOCK_EQUIPMENT_ID


@pytest.mark.parametrize("discovered", DISCOVERED_WITHOUT_TELEGRAM)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_discovery_without_telegram_validates(
    hass: HomeAssistant, discovered: EarnEP1Device
) -> None:
    """Test discovery that missed the telegram validates on confirm."""
    with patch(DISCOVER_PATH, return_value=[discovered]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SERIAL] == MOCK_SERIAL
    assert result["result"].unique_id == MOCK_EQUIPMENT_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_discovery_no_serial_validate_fails(
    hass: HomeAssistant,
) -> None:
    """Test discovery without serial aborts when validation also fails."""
    with patch(
        DISCOVER_PATH,
        return_value=[
            _mock_device(serial=None, equipment_id=None, seen_packet_types=frozenset())
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_discovery_no_serial_oserror(hass: HomeAssistant) -> None:
    """Test discovery without serial aborts on OSError during validation."""
    with patch(
        DISCOVER_PATH,
        return_value=[
            _mock_device(serial=None, equipment_id=None, seen_packet_types=frozenset())
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, side_effect=OSError("Address in use")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_discovery_no_serial_unexpected_error(
    hass: HomeAssistant,
) -> None:
    """Test discovery without serial aborts on unexpected error during validation."""
    with patch(
        DISCOVER_PATH,
        return_value=[
            _mock_device(serial=None, equipment_id=None, seen_packet_types=frozenset())
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, side_effect=RuntimeError("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_discovery_timeout_shows_manual_form(
    hass: HomeAssistant,
) -> None:
    """Test user flow falls back to manual form when discovery times out.

    Then recovers.
    """
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"EARN-E P1 ({MOCK_HOST})"
    assert result["data"] == {CONF_HOST: MOCK_HOST, CONF_SERIAL: MOCK_SERIAL}
    assert result["result"].unique_id == MOCK_EQUIPMENT_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_entry_meter_without_equipment_id(hass: HomeAssistant) -> None:
    """Test a meter that sends no equipment ID is keyed on the dongle serial."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, return_value=_mock_device(equipment_id=None)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_SERIAL


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_entry_validation_timeout_then_retry(hass: HomeAssistant) -> None:
    """Test manual entry: validation timeout shows error, retry succeeds."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (OSError("Address in use"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_entry_validation_errors(
    hass: HomeAssistant, side_effect: Exception, error: str
) -> None:
    """Test manual entry errors show correct error, retry succeeds."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, side_effect=side_effect):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_entry_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test manual entry of a swapped dongle updates the entry for its meter."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(
        VALIDATE_PATH,
        return_value=_mock_device(host=MOCK_NEW_HOST, serial=MOCK_NEW_SERIAL),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_NEW_HOST}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {
        CONF_HOST: MOCK_NEW_HOST,
        CONF_SERIAL: MOCK_NEW_SERIAL,
    }
    assert mock_config_entry.title == f"EARN-E P1 ({MOCK_NEW_HOST})"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_entry_legacy_entry(
    hass: HomeAssistant, mock_legacy_config_entry: MockConfigEntry
) -> None:
    """Test manual entry updates an entry still keyed on the dongle."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, return_value=_mock_device(host=MOCK_NEW_HOST)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_NEW_HOST}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_legacy_config_entry.data[CONF_HOST] == MOCK_NEW_HOST
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    "equipment_id",
    [
        pytest.param("REPLACED", id="meter_replaced"),
        pytest.param(None, id="no_equipment_id"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_entry_matches_dongle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    equipment_id: str | None,
) -> None:
    """Test manual entry falls back to the dongle when the meter does not match."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(
        VALIDATE_PATH,
        return_value=_mock_device(host=MOCK_NEW_HOST, equipment_id=equipment_id),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_NEW_HOST}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == MOCK_NEW_HOST
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_entry_prefers_meter_over_dongle(
    hass: HomeAssistant, mock_legacy_config_entry: MockConfigEntry
) -> None:
    """Test manual entry updates the entry for the meter over one for the dongle."""
    meter_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"EARN-E P1 ({MOCK_HOST_2})",
        data={CONF_HOST: MOCK_HOST_2, CONF_SERIAL: MOCK_SERIAL_2},
        unique_id=MOCK_EQUIPMENT_ID,
        minor_version=2,
    )
    meter_entry.add_to_hass(hass)

    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(VALIDATE_PATH, return_value=_mock_device(host=MOCK_NEW_HOST)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_NEW_HOST}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert meter_entry.data == {CONF_HOST: MOCK_NEW_HOST, CONF_SERIAL: MOCK_SERIAL}
    assert mock_legacy_config_entry.data[CONF_HOST] == MOCK_HOST


@pytest.mark.usefixtures("mock_setup_entry")
async def test_discovery_confirm_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test discovery confirm aborts when device is already configured."""
    with patch(DISCOVER_PATH, return_value=[_mock_device()]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discover_uses_shared_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
) -> None:
    """Test _async_discover uses shared listener when available."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_listener.discover = AsyncMock(
        return_value=[
            _mock_device(
                host="192.168.1.200", serial="AABBCCDDEEFF", equipment_id="OTHER"
            )
        ]
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    mock_listener.discover.assert_called_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_discover_without_shared_listener(hass: HomeAssistant) -> None:
    """Test _async_discover uses library discover when no shared listener."""
    with patch(DISCOVER_PATH, return_value=[_mock_device()]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_discover_without_shared_listener_oserror(hass: HomeAssistant) -> None:
    """Test _async_discover falls back to manual form on OSError, then succeeds."""
    with patch(DISCOVER_PATH, side_effect=OSError("Address in use")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_validate_uses_shared_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
) -> None:
    """Test _async_validate_host uses shared listener when available."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    other_host = "192.168.1.200"
    mock_listener.discover = AsyncMock(return_value=[])
    mock_listener.validate = AsyncMock(
        return_value=_mock_device(
            host=other_host, serial="AABBCCDDEEFF", equipment_id="OTHER"
        )
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: other_host}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "OTHER"
    mock_listener.validate.assert_called_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_validate_without_shared_listener(hass: HomeAssistant) -> None:
    """Test _async_validate_host uses library validate when no shared listener."""
    with patch(DISCOVER_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["step_id"] == "user"

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: MOCK_HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_EQUIPMENT_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_discovery_new_device(hass: HomeAssistant) -> None:
    """Test DHCP discovers a new device and creates a config entry."""
    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: MOCK_HOST, CONF_SERIAL: MOCK_SERIAL}
    assert result["result"].unique_id == MOCK_EQUIPMENT_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_discovery_swapped_dongle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP moves the entry for a meter onto its swapped dongle."""
    dhcp_info = DhcpServiceInfo(
        ip=MOCK_NEW_HOST,
        hostname=MOCK_HOSTNAME,
        macaddress=MOCK_NEW_MAC,
    )

    discovery_key = DiscoveryKey(domain="dhcp", key=MOCK_NEW_MAC, version=1)

    with patch(
        VALIDATE_PATH,
        return_value=_mock_device(host=MOCK_NEW_HOST, serial=MOCK_NEW_SERIAL),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_DHCP,
                "discovery_key": discovery_key,
            },
            data=dhcp_info,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {
        CONF_HOST: MOCK_NEW_HOST,
        CONF_SERIAL: MOCK_NEW_SERIAL,
    }
    assert mock_config_entry.title == f"EARN-E P1 ({MOCK_NEW_HOST})"
    assert mock_config_entry.discovery_keys == {"dhcp": (discovery_key,)}


@pytest.mark.parametrize(
    ("validate_mock", "reason"),
    [
        ({"return_value": None}, "cannot_connect"),
        ({"side_effect": OSError("no socket")}, "cannot_connect"),
        ({"side_effect": RuntimeError("boom")}, "unknown"),
    ],
    ids=["timeout", "oserror", "unexpected_error"],
)
async def test_dhcp_discovery_validate_failures(
    hass: HomeAssistant, validate_mock: dict[str, Any], reason: str
) -> None:
    """Test DHCP validation failures abort with the expected reason."""
    with patch(VALIDATE_PATH, **validate_mock):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_dhcp_discovery_updates_ip_by_mac(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test DHCP fast path: the dongle's MAC updates IP without validating."""
    dhcp_info = DhcpServiceInfo(
        ip=MOCK_NEW_HOST,
        hostname=MOCK_HOSTNAME,
        macaddress=MOCK_MAC,
    )

    discovery_key = DiscoveryKey(domain="dhcp", key=MOCK_MAC, version=1)

    with patch(VALIDATE_PATH) as mock_validate:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_DHCP,
                "discovery_key": discovery_key,
            },
            data=dhcp_info,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {
        CONF_HOST: MOCK_NEW_HOST,
        CONF_SERIAL: MOCK_SERIAL,
    }
    assert mock_config_entry.title == f"EARN-E P1 ({MOCK_NEW_HOST})"
    assert mock_config_entry.discovery_keys == {"dhcp": (discovery_key,)}
    mock_validate.assert_not_called()


@pytest.mark.parametrize(
    "unique_id",
    [
        pytest.param(MOCK_EQUIPMENT_ID, id="meter"),
        pytest.param(MOCK_SERIAL, id="legacy_dongle"),
    ],
)
async def test_dhcp_discovery_aborts_for_ignored_entry(
    hass: HomeAssistant, unique_id: str
) -> None:
    """Test DHCP discovery does not re-offer a device the user ignored."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_IGNORE,
        unique_id=unique_id,
        data={},
    )
    entry.add_to_hass(hass)

    with patch(VALIDATE_PATH, return_value=_mock_device()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
