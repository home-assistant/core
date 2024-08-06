"""Test config flow."""

from collections.abc import Generator
from ipaddress import IPv4Address, ip_address
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch

from pyatv import exceptions
from pyatv.const import PairingRequirement, Protocol
import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.apple_tv import CONF_ADDRESS, config_flow
from homeassistant.components.apple_tv.const import (
    CONF_IDENTIFIERS,
    CONF_START_OFF,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import airplay_service, create_conf, mrp_service, raop_service

from tests.common import MockConfigEntry

DMAP_SERVICE = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname="mock_hostname",
    port=None,
    type="_touch-able._tcp.local.",
    name="dmapid._touch-able._tcp.local.",
    properties={"CtlN": "Apple TV"},
)


RAOP_SERVICE = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname="mock_hostname",
    port=None,
    type="_raop._tcp.local.",
    name="AABBCCDDEEFF@Master Bed._raop._tcp.local.",
    properties={"am": "AppleTV11,1"},
)


@pytest.fixture(autouse=True)
def zero_aggregation_time() -> Generator[None]:
    """Prevent the aggregation time from delaying the tests."""
    with patch.object(config_flow, "DISCOVERY_AGGREGATION_TIME", 0):
        yield


@pytest.fixture(autouse=True)
def use_mocked_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Mock zeroconf in all tests."""


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.apple_tv.async_setup_entry", return_value=True
    ):
        yield


# User Flows


@pytest.mark.usefixtures("mrp_device")
async def test_user_input_device_not_found(hass: HomeAssistant) -> None:
    """Test when user specifies a non-existing device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "none"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "no_devices_found"}


async def test_user_input_unexpected_error(
    hass: HomeAssistant, mock_scan: AsyncMock
) -> None:
    """Test that unexpected error yields an error message."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_scan.side_effect = Exception
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "dummy"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("full_device", "pairing")
async def test_user_adds_full_device(hass: HomeAssistant) -> None:
    """Test adding device with all services."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "MRP Device"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["description_placeholders"] == {
        "name": "MRP Device",
        "type": "Unknown",
    }

    result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result3["type"] is FlowResultType.FORM
    assert result3["description_placeholders"] == {"protocol": "MRP"}

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": 1111}
    )
    assert result4["type"] is FlowResultType.FORM
    assert result4["description_placeholders"] == {"protocol": "DMAP", "pin": "1111"}

    result5 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result5["type"] is FlowResultType.FORM
    assert result5["description_placeholders"] == {"protocol": "AirPlay"}

    result6 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": 1234}
    )
    assert result6["type"] is FlowResultType.CREATE_ENTRY
    assert result6["data"] == {
        "address": "127.0.0.1",
        "credentials": {
            Protocol.DMAP.value: "dmap_creds",
            Protocol.MRP.value: "mrp_creds",
            Protocol.AirPlay.value: "airplay_creds",
        },
        "identifiers": ["mrpid", "dmapid", "airplayid"],
        "name": "MRP Device",
    }


@pytest.mark.usefixtures("dmap_device", "dmap_pin", "pairing")
async def test_user_adds_dmap_device(hass: HomeAssistant) -> None:
    """Test adding device with only DMAP service."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "DMAP Device"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["description_placeholders"] == {
        "name": "DMAP Device",
        "type": "Unknown",
    }

    result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result3["type"] is FlowResultType.FORM
    assert result3["description_placeholders"] == {"pin": "1111", "protocol": "DMAP"}

    result6 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": 1234}
    )
    assert result6["type"] is FlowResultType.CREATE_ENTRY
    assert result6["data"] == {
        "address": "127.0.0.1",
        "credentials": {Protocol.DMAP.value: "dmap_creds"},
        "identifiers": ["dmapid"],
        "name": "DMAP Device",
    }


@pytest.mark.usefixtures("dmap_device", "dmap_pin")
async def test_user_adds_dmap_device_failed(
    hass: HomeAssistant, pairing: AsyncMock
) -> None:
    """Test adding DMAP device where remote device did not attempt to pair."""
    pairing.always_fail = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "DMAP Device"},
    )

    await hass.config_entries.flow.async_configure(result["flow_id"], {})

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "device_did_not_pair"


@pytest.mark.usefixtures("dmap_device_with_credentials", "mock_scan")
async def test_user_adds_device_with_ip_filter(hass: HomeAssistant) -> None:
    """Test add device filtering by IP."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "127.0.0.1"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["description_placeholders"] == {
        "name": "DMAP Device",
        "type": "Unknown",
    }


@pytest.mark.parametrize("pairing_requirement", [(PairingRequirement.NotNeeded)])
@pytest.mark.usefixtures("dmap_with_requirement", "pairing_mock")
async def test_user_pair_no_interaction(hass: HomeAssistant) -> None:
    """Test pairing service without user interaction."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "DMAP Device"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["data"] == {
        "address": "127.0.0.1",
        "credentials": {Protocol.DMAP.value: None},
        "identifiers": ["dmapid"],
        "name": "DMAP Device",
    }


async def test_user_adds_device_by_ip_uses_unicast_scan(
    hass: HomeAssistant, mock_scan: AsyncMock
) -> None:
    """Test add device by IP-address, verify unicast scan is used."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "127.0.0.1"},
    )

    assert str(mock_scan.hosts[0]) == "127.0.0.1"


@pytest.mark.usefixtures("mrp_device")
async def test_user_adds_existing_device(hass: HomeAssistant) -> None:
    """Test that it is not possible to add existing device."""
    MockConfigEntry(domain="apple_tv", unique_id="mrpid").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "127.0.0.1"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "already_configured"}


@pytest.mark.usefixtures("mrp_device")
async def test_user_connection_failed(
    hass: HomeAssistant, pairing_mock: AsyncMock
) -> None:
    """Test error message when connection to device fails."""
    pairing_mock.begin.side_effect = exceptions.ConnectionFailedError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "MRP Device"},
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "setup_failed"


@pytest.mark.usefixtures("mrp_device")
async def test_user_start_pair_error_failed(
    hass: HomeAssistant, pairing_mock: AsyncMock
) -> None:
    """Test initiating pairing fails."""
    pairing_mock.begin.side_effect = exceptions.PairingError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "MRP Device"},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "invalid_auth"


@pytest.mark.usefixtures("airplay_device_with_password", "pairing_mock")
async def test_user_pair_service_with_password(hass: HomeAssistant) -> None:
    """Test pairing with service requiring a password (not supported)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "AirPlay Device"},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "password"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "setup_failed"


@pytest.mark.parametrize("pairing_requirement", [(PairingRequirement.Disabled)])
@pytest.mark.usefixtures("dmap_with_requirement", "pairing_mock")
async def test_user_pair_disabled_service(hass: HomeAssistant) -> None:
    """Test pairing with disabled service (is ignored with message)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "DMAP Device"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "protocol_disabled"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "setup_failed"


@pytest.mark.parametrize("pairing_requirement", [(PairingRequirement.Unsupported)])
@pytest.mark.usefixtures("dmap_with_requirement", "pairing_mock")
async def test_user_pair_ignore_unsupported(hass: HomeAssistant) -> None:
    """Test pairing with disabled service (is ignored silently)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "DMAP Device"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "setup_failed"


@pytest.mark.usefixtures("mrp_device")
async def test_user_pair_invalid_pin(
    hass: HomeAssistant, pairing_mock: AsyncMock
) -> None:
    """Test pairing with invalid pin."""
    pairing_mock.finish.side_effect = exceptions.PairingError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "MRP Device"},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"pin": 1111},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


@pytest.mark.usefixtures("mrp_device")
async def test_user_pair_unexpected_error(
    hass: HomeAssistant, pairing_mock: AsyncMock
) -> None:
    """Test unexpected error when entering PIN code."""

    pairing_mock.finish.side_effect = Exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "MRP Device"},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"pin": 1111},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("mrp_device")
async def test_user_pair_backoff_error(
    hass: HomeAssistant, pairing_mock: AsyncMock
) -> None:
    """Test that backoff error is displayed in case device requests it."""
    pairing_mock.begin.side_effect = exceptions.BackOffError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "MRP Device"},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "backoff"


@pytest.mark.usefixtures("mrp_device")
async def test_user_pair_begin_unexpected_error(
    hass: HomeAssistant, pairing_mock: AsyncMock
) -> None:
    """Test unexpected error during start of pairing."""
    pairing_mock.begin.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "MRP Device"},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unknown"


@pytest.mark.usefixtures("airplay_with_disabled_mrp", "pairing")
async def test_ignores_disabled_service(hass: HomeAssistant) -> None:
    """Test adding device with only DMAP service."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Find based on mrpid (but do not pair that service since it's disabled)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "mrpid"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {
        "name": "AirPlay Device",
        "type": "Unknown",
    }

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] is FlowResultType.FORM
    assert result2["description_placeholders"] == {"protocol": "AirPlay"}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": 1111}
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        "address": "127.0.0.1",
        "credentials": {
            Protocol.AirPlay.value: "airplay_creds",
        },
        "identifiers": ["mrpid", "airplayid"],
        "name": "AirPlay Device",
    }


# Zeroconf


async def test_zeroconf_unsupported_service_aborts(hass: HomeAssistant) -> None:
    """Test discovering unsupported zeroconf service."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            type="_dummy._tcp.local.",
            properties={},
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.usefixtures("mrp_device", "pairing")
async def test_zeroconf_add_mrp_device(hass: HomeAssistant) -> None:
    """Test add MRP device discovered by zeroconf."""
    unrelated_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.2"),
            ip_addresses=[ip_address("127.0.0.2")],
            hostname="mock_hostname",
            port=None,
            name="Kitchen",
            properties={"UniqueIdentifier": "unrelated", "Name": "Kitchen"},
            type="_mediaremotetv._tcp.local.",
        ),
    )
    assert unrelated_result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            port=None,
            name="Kitchen",
            properties={"UniqueIdentifier": "mrpid", "Name": "Kitchen"},
            type="_mediaremotetv._tcp.local.",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {
        "name": "MRP Device",
        "type": "Unknown",
    }

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["description_placeholders"] == {"protocol": "MRP"}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": 1111}
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        "address": "127.0.0.1",
        "credentials": {Protocol.MRP.value: "mrp_creds"},
        "identifiers": ["mrpid"],
        "name": "MRP Device",
    }


@pytest.mark.usefixtures("dmap_device", "dmap_pin", "pairing")
async def test_zeroconf_add_dmap_device(hass: HomeAssistant) -> None:
    """Test add DMAP device discovered by zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {
        "name": "DMAP Device",
        "type": "Unknown",
    }

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["description_placeholders"] == {"protocol": "DMAP", "pin": "1111"}

    result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        "address": "127.0.0.1",
        "credentials": {Protocol.DMAP.value: "dmap_creds"},
        "identifiers": ["dmapid"],
        "name": "DMAP Device",
    }


async def test_zeroconf_ip_change(hass: HomeAssistant, mock_scan: AsyncMock) -> None:
    """Test that the config entry gets updated when the ip changes and reloads."""
    entry = MockConfigEntry(
        domain="apple_tv", unique_id="mrpid", data={CONF_ADDRESS: "127.0.0.2"}
    )
    unrelated_entry = MockConfigEntry(
        domain="apple_tv", unique_id="unrelated", data={CONF_ADDRESS: "127.0.0.2"}
    )
    unrelated_entry.add_to_hass(hass)
    entry.add_to_hass(hass)
    mock_scan.result = [
        create_conf(
            IPv4Address("127.0.0.1"), "Device", mrp_service(), airplay_service()
        )
    ]

    with patch(
        "homeassistant.components.apple_tv.async_setup_entry", return_value=True
    ) as mock_async_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=DMAP_SERVICE,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_async_setup.mock_calls) == 2
    assert entry.data[CONF_ADDRESS] == "127.0.0.1"
    assert unrelated_entry.data[CONF_ADDRESS] == "127.0.0.2"


async def test_zeroconf_ip_change_after_ip_conflict_with_ignored_entry(
    hass: HomeAssistant, mock_scan: AsyncMock
) -> None:
    """Test that the config entry gets updated when the ip changes and reloads."""
    entry = MockConfigEntry(
        domain="apple_tv", unique_id="mrpid", data={CONF_ADDRESS: "127.0.0.2"}
    )
    ignored_entry = MockConfigEntry(
        domain="apple_tv",
        unique_id="unrelated",
        data={CONF_ADDRESS: "127.0.0.2"},
        source=config_entries.SOURCE_IGNORE,
    )
    ignored_entry.add_to_hass(hass)
    entry.add_to_hass(hass)
    mock_scan.result = [
        create_conf(
            IPv4Address("127.0.0.1"), "Device", mrp_service(), airplay_service()
        )
    ]

    with patch(
        "homeassistant.components.apple_tv.async_setup_entry", return_value=True
    ) as mock_async_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=DMAP_SERVICE,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_async_setup.mock_calls) == 1
    assert entry.data[CONF_ADDRESS] == "127.0.0.1"
    assert ignored_entry.data[CONF_ADDRESS] == "127.0.0.2"


async def test_zeroconf_ip_change_via_secondary_identifier(
    hass: HomeAssistant, mock_scan: AsyncMock
) -> None:
    """Test that the config entry gets updated when the ip changes and reloads.

    Instead of checking only the unique id, all the identifiers
    in the config entry are checked
    """
    entry = MockConfigEntry(
        domain="apple_tv",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={CONF_IDENTIFIERS: ["mrpid"], CONF_ADDRESS: "127.0.0.2"},
    )
    unrelated_entry = MockConfigEntry(
        domain="apple_tv", unique_id="unrelated", data={CONF_ADDRESS: "127.0.0.2"}
    )
    unrelated_entry.add_to_hass(hass)
    entry.add_to_hass(hass)
    mock_scan.result = [
        create_conf(
            IPv4Address("127.0.0.1"), "Device", mrp_service(), airplay_service()
        )
    ]

    with patch(
        "homeassistant.components.apple_tv.async_setup_entry", return_value=True
    ) as mock_async_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=DMAP_SERVICE,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_async_setup.mock_calls) == 2
    assert entry.data[CONF_ADDRESS] == "127.0.0.1"
    assert unrelated_entry.data[CONF_ADDRESS] == "127.0.0.2"
    assert set(entry.data[CONF_IDENTIFIERS]) == {"airplayid", "mrpid"}


async def test_zeroconf_updates_identifiers_for_ignored_entries(
    hass: HomeAssistant, mock_scan: AsyncMock
) -> None:
    """Test that an ignored config entry gets updated when the ip changes.

    Instead of checking only the unique id, all the identifiers
    in the config entry are checked
    """
    entry = MockConfigEntry(
        domain="apple_tv",
        unique_id="aa:bb:cc:dd:ee:ff",
        source=config_entries.SOURCE_IGNORE,
        data={CONF_IDENTIFIERS: ["mrpid"], CONF_ADDRESS: "127.0.0.2"},
    )
    unrelated_entry = MockConfigEntry(
        domain="apple_tv", unique_id="unrelated", data={CONF_ADDRESS: "127.0.0.2"}
    )
    unrelated_entry.add_to_hass(hass)
    entry.add_to_hass(hass)
    mock_scan.result = [
        create_conf(
            IPv4Address("127.0.0.1"), "Device", mrp_service(), airplay_service()
        )
    ]

    with patch(
        "homeassistant.components.apple_tv.async_setup_entry", return_value=True
    ) as mock_async_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=DMAP_SERVICE,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert (
        len(mock_async_setup.mock_calls) == 0
    )  # Should not be called because entry is ignored
    assert entry.data[CONF_ADDRESS] == "127.0.0.1"
    assert unrelated_entry.data[CONF_ADDRESS] == "127.0.0.2"
    assert set(entry.data[CONF_IDENTIFIERS]) == {"airplayid", "mrpid"}


@pytest.mark.usefixtures("dmap_device")
async def test_zeroconf_add_existing_aborts(hass: HomeAssistant) -> None:
    """Test start new zeroconf flow while existing flow is active aborts."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.usefixtures("mock_scan")
async def test_zeroconf_add_but_device_not_found(hass: HomeAssistant) -> None:
    """Test add device which is not found with another scan."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("dmap_device")
async def test_zeroconf_add_existing_device(hass: HomeAssistant) -> None:
    """Test add already existing device from zeroconf."""
    MockConfigEntry(domain="apple_tv", unique_id="dmapid").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_unexpected_error(
    hass: HomeAssistant, mock_scan: AsyncMock
) -> None:
    """Test unexpected error aborts in zeroconf."""
    mock_scan.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_zeroconf_abort_if_other_in_progress(
    hass: HomeAssistant, mock_scan: AsyncMock
) -> None:
    """Test discovering unsupported zeroconf service."""
    mock_scan.result = [
        create_conf(IPv4Address("127.0.0.1"), "Device", airplay_service())
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            port=None,
            type="_airplay._tcp.local.",
            name="Kitchen",
            properties={"deviceid": "airplayid"},
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    mock_scan.result = [
        create_conf(
            IPv4Address("127.0.0.1"), "Device", mrp_service(), airplay_service()
        )
    ]

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            port=None,
            type="_mediaremotetv._tcp.local.",
            name="Kitchen",
            properties={"UniqueIdentifier": "mrpid", "Name": "Kitchen"},
        ),
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


@pytest.mark.usefixtures("pairing", "mock_zeroconf")
async def test_zeroconf_missing_device_during_protocol_resolve(
    hass: HomeAssistant, mock_scan: AsyncMock
) -> None:
    """Test discovery after service been added to existing flow with missing device."""
    mock_scan.result = [
        create_conf(IPv4Address("127.0.0.1"), "Device", airplay_service())
    ]

    # Find device with AirPlay service and set up flow for it
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            port=None,
            type="_airplay._tcp.local.",
            name="Kitchen",
            properties={"deviceid": "airplayid"},
        ),
    )

    mock_scan.result = [
        create_conf(
            IPv4Address("127.0.0.1"), "Device", mrp_service(), airplay_service()
        )
    ]

    # Find the same device again, but now also with MRP service. The first flow should
    # be updated with the MRP service.
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            port=None,
            type="_mediaremotetv._tcp.local.",
            name="Kitchen",
            properties={"UniqueIdentifier": "mrpid", "Name": "Kitchen"},
        ),
    )

    mock_scan.result = []

    # Number of services found during initial scan (1) will not match the updated count
    # (2), so it will trigger a re-scan to find all services. This will fail as no
    # device is found.
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "device_not_found"


@pytest.mark.usefixtures("pairing", "mock_zeroconf")
async def test_zeroconf_additional_protocol_resolve_failure(
    hass: HomeAssistant, mock_scan: AsyncMock
) -> None:
    """Test discovery with missing service."""
    mock_scan.result = [
        create_conf(IPv4Address("127.0.0.1"), "Device", airplay_service())
    ]

    # Find device with AirPlay service and set up flow for it
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            port=None,
            type="_airplay._tcp.local.",
            name="Kitchen",
            properties={"deviceid": "airplayid"},
        ),
    )

    mock_scan.result = [
        create_conf(
            IPv4Address("127.0.0.1"), "Device", mrp_service(), airplay_service()
        )
    ]

    # Find the same device again, but now also with MRP service. The first flow should
    # be updated with the MRP service.
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            port=None,
            type="_mediaremotetv._tcp.local.",
            name="Kitchen",
            properties={"UniqueIdentifier": "mrpid", "Name": "Kitchen"},
        ),
    )

    mock_scan.result = [
        create_conf(IPv4Address("127.0.0.1"), "Device", airplay_service())
    ]

    # Number of services found during initial scan (1) will not match the updated count
    # (2), so it will trigger a re-scan to find all services. This will however fail
    # due to only one of the services found, yielding an error message.
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "inconsistent_device"


@pytest.mark.usefixtures("pairing", "mock_zeroconf")
async def test_zeroconf_pair_additionally_found_protocols(
    hass: HomeAssistant, mock_scan: AsyncMock
) -> None:
    """Test discovered protocols are merged to original flow."""
    mock_scan.result = [
        create_conf(IPv4Address("127.0.0.1"), "Device", airplay_service())
    ]

    # Find device with AirPlay service and set up flow for it
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            port=None,
            type="_airplay._tcp.local.",
            name="Kitchen",
            properties={"deviceid": "airplayid"},
        ),
    )
    assert result["type"] is FlowResultType.FORM
    await hass.async_block_till_done()

    mock_scan.result = [
        create_conf(
            IPv4Address("127.0.0.1"), "Device", raop_service(), airplay_service()
        )
    ]

    # Find the same device again, but now also with RAOP service. The first flow should
    # be updated with the RAOP service.
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=RAOP_SERVICE,
    )
    await hass.async_block_till_done()

    mock_scan.result = [
        create_conf(
            IPv4Address("127.0.0.1"),
            "Device",
            raop_service(),
            mrp_service(),
            airplay_service(),
        )
    ]

    # Find the same device again, but now also with MRP service. The first flow should
    # be updated with the MRP service.
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            port=None,
            type="_mediaremotetv._tcp.local.",
            name="Kitchen",
            properties={"UniqueIdentifier": "mrpid", "Name": "Kitchen"},
        ),
    )
    await hass.async_block_till_done()

    # Verify that all protocols are paired
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "pair_no_pin"
    assert result2["description_placeholders"] == {"pin": ANY, "protocol": "RAOP"}

    # Verify that all protocols are paired
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "pair_with_pin"
    assert result3["description_placeholders"] == {"protocol": "MRP"}

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"pin": 1234},
    )
    assert result4["type"] is FlowResultType.FORM
    assert result4["step_id"] == "pair_with_pin"
    assert result4["description_placeholders"] == {"protocol": "AirPlay"}

    result5 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"pin": 1234},
    )
    assert result5["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("pairing", "mock_zeroconf")
async def test_zeroconf_mismatch(hass: HomeAssistant, mock_scan: AsyncMock) -> None:
    """Test the technically possible case where a protocol has no service.

    This could happen in case of mDNS issues.
    """
    mock_scan.result = [
        create_conf(IPv4Address("127.0.0.1"), "Device", airplay_service())
    ]
    mock_scan.result[0].get_service = Mock(return_value=None)

    # Find device with AirPlay service and set up flow for it
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            port=None,
            type="_airplay._tcp.local.",
            name="Kitchen",
            properties={"deviceid": "airplayid"},
        ),
    )
    assert result["type"] is FlowResultType.FORM
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "setup_failed"


# Re-configuration


@pytest.mark.usefixtures("mrp_device", "pairing")
async def test_reconfigure_update_credentials(hass: HomeAssistant) -> None:
    """Test that reconfigure flow updates config entry."""
    config_entry = MockConfigEntry(
        domain="apple_tv", unique_id="mrpid", data={"identifiers": ["mrpid"]}
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth"},
        data={"identifier": "mrpid", "name": "apple tv"},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["description_placeholders"] == {"protocol": "MRP"}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": 1111}
    )
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"

    assert config_entry.data == {
        "address": "127.0.0.1",
        "name": "MRP Device",
        "credentials": {Protocol.MRP.value: "mrp_creds"},
        "identifiers": ["mrpid"],
    }


# Options


async def test_option_start_off(hass: HomeAssistant) -> None:
    """Test start off-option flag."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="dmapid", options={"start_off": False}
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_START_OFF: True}
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY

    assert config_entry.options[CONF_START_OFF]


async def test_zeroconf_rejects_ipv6(hass: HomeAssistant) -> None:
    """Test zeroconf discovery rejects ipv6."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("fd00::b27c:63bb:cc85:4ea0"),
            ip_addresses=[ip_address("fd00::b27c:63bb:cc85:4ea0")],
            hostname="mock_hostname",
            port=None,
            type="_touch-able._tcp.local.",
            name="dmapid._touch-able._tcp.local.",
            properties={"CtlN": "Apple TV"},
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ipv6_not_supported"
