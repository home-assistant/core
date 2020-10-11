"""Test config flow."""

from pyatv import exceptions
from pyatv.const import Protocol
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.apple_tv.const import CONF_START_OFF, DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry

DMAP_SERVICE = {
    "type": "_touch-able._tcp.local.",
    "name": "dmapid.something",
    "properties": {"CtlN": "Apple TV"},
}


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.apple_tv.async_setup_entry", return_value=True
    ):
        yield


# User Flows


async def test_user_input_device_not_found(hass, mrp_device):
    """Test when user specifies a non-existing device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["description_placeholders"] == {"devices": "`MRP Device (127.0.0.1)`"}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "none"},
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "no_devices_found"}


async def test_user_input_unexpected_error(hass, mock_scan):
    """Test that unexpected error yields an error message."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_scan.side_effect = Exception
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "dummy"},
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_user_adds_full_device(hass, full_device, pairing):
    """Test adding device with all services."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "MRP Device"},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["description_placeholders"] == {"name": "MRP Device"}

    result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result3["description_placeholders"] == {"protocol": "MRP"}

    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": 1111}
    )
    assert result4["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result4["description_placeholders"] == {"protocol": "DMAP", "pin": 1111}

    result5 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result5["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result5["description_placeholders"] == {"protocol": "AirPlay"}

    result6 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": 1234}
    )
    assert result6["type"] == "create_entry"
    assert result6["data"] == {
        "address": "127.0.0.1",
        "credentials": {
            Protocol.DMAP.value: "dmap_creds",
            Protocol.MRP.value: "mrp_creds",
            Protocol.AirPlay.value: "airplay_creds",
        },
        "name": "MRP Device",
        "protocol": Protocol.MRP.value,
    }


async def test_user_adds_dmap_device(hass, dmap_device, dmap_pin, pairing):
    """Test adding device with only DMAP service."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "DMAP Device"},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["description_placeholders"] == {"name": "DMAP Device"}

    result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result3["description_placeholders"] == {"pin": 1111, "protocol": "DMAP"}

    result6 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": 1234}
    )
    assert result6["type"] == "create_entry"
    assert result6["data"] == {
        "address": "127.0.0.1",
        "credentials": {Protocol.DMAP.value: "dmap_creds"},
        "name": "DMAP Device",
        "protocol": Protocol.DMAP.value,
    }


async def test_user_adds_dmap_device_failed(hass, dmap_device, dmap_pin, pairing):
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
    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "device_did_not_pair"


async def test_user_adds_device_with_credentials(hass, dmap_device_with_credentials):
    """Test adding DMAP device with existing credentials (home sharing)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "DMAP Device"},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["description_placeholders"] == {"name": "DMAP Device"}

    result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result3["type"] == "create_entry"
    assert result3["data"] == {
        "address": "127.0.0.1",
        "credentials": {Protocol.DMAP.value: "dummy_creds"},
        "name": "DMAP Device",
        "protocol": Protocol.DMAP.value,
    }


async def test_user_adds_device_with_ip_filter(
    hass, dmap_device_with_credentials, mock_scan
):
    """Test add device filtering by IP."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "127.0.0.1"},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["description_placeholders"] == {"name": "DMAP Device"}

    result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result3["type"] == "create_entry"
    assert result3["data"] == {
        "address": "127.0.0.1",
        "credentials": {Protocol.DMAP.value: "dummy_creds"},
        "name": "DMAP Device",
        "protocol": Protocol.DMAP.value,
    }


async def test_user_adds_device_by_ip_uses_unicast_scan(hass, mock_scan):
    """Test add device by IP-address, verify unicast scan is used."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "127.0.0.1"},
    )

    assert str(mock_scan.hosts[0]) == "127.0.0.1"


async def test_user_adds_existing_device(hass, mrp_device):
    """Test that it is not possible to add existing device."""
    MockConfigEntry(domain="apple_tv", unique_id="mrpid").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "127.0.0.1"},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "already_configured"}


async def test_user_adds_unusable_device(hass, airplay_device):
    """Test that it is not possible to add pure AirPlay device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device_input": "AirPlay Device"},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "no_usable_service"}


async def test_user_connection_failed(hass, mrp_device, pairing_mock):
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
    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "invalid_config"


async def test_user_start_pair_error_failed(hass, mrp_device, pairing_mock):
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
    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "invalid_auth"


async def test_user_pair_invalid_pin(hass, mrp_device, pairing_mock):
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
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_pair_unexpected_error(hass, mrp_device, pairing_mock):
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
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_user_pair_backoff_error(hass, mrp_device, pairing_mock):
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
    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "backoff"


async def test_user_pair_begin_unexpected_error(hass, mrp_device, pairing_mock):
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
    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "unknown"


# Zeroconf


async def test_zeroconf_unsupported_service_aborts(hass):
    """Test discovering unsupported zeroconf service."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "type": "_dummy._tcp.local.",
            "properties": {},
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"


async def test_zeroconf_add_mrp_device(hass, mrp_device, pairing):
    """Test add MRP device discovered by zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "type": "_mediaremotetv._tcp.local.",
            "properties": {"UniqueIdentifier": "mrpid", "Name": "Kitchen"},
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["description_placeholders"] == {"name": "MRP Device"}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["description_placeholders"] == {"protocol": "MRP"}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": 1111}
    )
    assert result3["type"] == "create_entry"
    assert result3["data"] == {
        "address": "127.0.0.1",
        "credentials": {Protocol.MRP.value: "mrp_creds"},
        "name": "MRP Device",
        "protocol": Protocol.MRP.value,
    }


async def test_zeroconf_add_dmap_device(hass, dmap_device, dmap_pin, pairing):
    """Test add DMAP device discovered by zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["description_placeholders"] == {"name": "DMAP Device"}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["description_placeholders"] == {"protocol": "DMAP", "pin": 1111}

    result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result3["type"] == "create_entry"
    assert result3["data"] == {
        "address": "127.0.0.1",
        "credentials": {Protocol.DMAP.value: "dmap_creds"},
        "name": "DMAP Device",
        "protocol": Protocol.DMAP.value,
    }


async def test_zeroconf_add_existing_aborts(hass, dmap_device):
    """Test start new zeroconf flow while existing flow is active aborts."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_in_progress"


async def test_zeroconf_add_but_device_not_found(hass, mock_scan):
    """Test add device which is not found with another scan."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_devices_found"


async def test_zeroconf_add_existing_device(hass, dmap_device):
    """Test add already existing device from zeroconf."""
    MockConfigEntry(domain="apple_tv", unique_id="dmapid").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_unexpected_error(hass, mock_scan):
    """Test unexpected error aborts in zeroconf."""
    mock_scan.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DMAP_SERVICE
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"


# Re-configuration


async def test_reconfigure_update_credentials(hass, mrp_device, pairing):
    """Test that reconfigure flow updates config entry."""
    config_entry = MockConfigEntry(domain="apple_tv", unique_id="mrpid")
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
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["description_placeholders"] == {"protocol": "MRP"}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"pin": 1111}
    )
    assert result3["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result3["reason"] == "already_configured"

    assert config_entry.data == {
        "address": "127.0.0.1",
        "protocol": Protocol.MRP.value,
        "name": "MRP Device",
        "credentials": {Protocol.MRP.value: "mrp_creds"},
    }


async def test_reconfigure_ongoing_aborts(hass, mrp_device):
    """Test start additional reconfigure flow aborts."""
    data = {
        "identifier": "mrpid",
        "name": "Apple TV",
    }

    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=data
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=data
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_in_progress"


# Options


async def test_option_start_off(hass):
    """Test start off-option flag."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="dmapid", options={"start_off": False}
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_START_OFF: True}
    )
    assert result2["type"] == "create_entry"

    assert config_entry.options[CONF_START_OFF]
