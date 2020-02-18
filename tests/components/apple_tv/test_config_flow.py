"""Test config flow."""

from tests.common import MockConfigEntry, mock_coro

from pyatv import exceptions
from pyatv.const import Protocol

# User Flows


async def test_user_input_device_not_found(flow, mrp_device):
    """Test when user specifies a non-existing device."""
    (await flow().step_user(has_input=False)).gives_form_user(
        description_placeholders={"devices": "`MRP Device (127.0.0.1)`"}
    )

    (await flow().step_user(identifier="none")).gives_form_user(
        description_placeholders={"devices": "`MRP Device (127.0.0.1)`"},
        errors={"base": "device_not_found"},
    )


async def test_user_input_unexpected_error(flow, mock_scan):
    """Test that unexpected error yields an error message."""
    (await flow().step_user(has_input=False)).gives_form_user()

    mock_scan.side_effect = Exception

    (await flow().step_user(identifier="dummy")).gives_form_user(
        errors={"base": "unknown"}
    )


async def test_user_adds_full_device(flow, full_device, pairing):
    """Test adding device with all services."""
    (await flow().step_user(identifier="MRP Device")).gives_form_confirm(
        description_placeholders={"name": "MRP Device"}
    )

    (await flow().step_confirm()).gives_form_pair_with_pin(
        description_placeholders={"protocol": "MRP"}
    )

    (await flow().step_pair_with_pin(pin=1111)).gives_form_pair_no_pin(
        description_placeholders={"protocol": "DMAP", "pin": 1111}
    )

    (await flow().step_pair_no_pin()).gives_form_pair_with_pin(
        description_placeholders={"protocol": "AirPlay"}
    )

    (await flow().step_pair_with_pin(pin=1234)).gives_create_entry(
        {
            "identifier": "mrp_id",
            "address": "127.0.0.1",
            "protocol": Protocol.MRP.value,
            "name": "MRP Device",
            "credentials": {
                Protocol.MRP.value: "mrp_creds",
                Protocol.DMAP.value: "dmap_creds",
                Protocol.AirPlay.value: "airplay_creds",
            },
        }
    )


async def test_user_adds_dmap_device(flow, dmap_device, dmap_pin, pairing):
    """Test adding device with only DMAP service."""
    (await flow().step_user(identifier="DMAP Device")).gives_form_confirm(
        description_placeholders={"name": "DMAP Device"}
    )

    (await flow().step_confirm()).gives_form_pair_no_pin(
        description_placeholders={"protocol": "DMAP", "pin": 1111}
    )

    (await flow().step_pair_no_pin()).gives_create_entry(
        {
            "identifier": "dmap_id",
            "address": "127.0.0.1",
            "protocol": Protocol.DMAP.value,
            "name": "DMAP Device",
            "credentials": {Protocol.DMAP.value: "dmap_creds"},
        }
    )


async def test_user_adds_dmap_device_failed(flow, dmap_device, dmap_pin, pairing):
    """Test adding DMAP device where remote device did not attempt to pair."""
    pairing.always_fail = True

    (await flow().step_user(identifier="DMAP Device")).gives_form_confirm(
        description_placeholders={"name": "DMAP Device"}
    )

    (await flow().step_confirm()).gives_form_pair_no_pin(
        description_placeholders={"protocol": "DMAP", "pin": 1111}
    )

    (await flow().step_pair_no_pin()).gives_abort("device_did_not_pair")


async def test_user_adds_device_with_credentials(flow, dmap_device_with_credentials):
    """Test adding DMAP device with existing credentials (home sharing)."""
    (await flow().step_user(identifier="DMAP Device")).gives_form_confirm(
        description_placeholders={"name": "DMAP Device"}
    )

    (await flow().step_confirm()).gives_create_entry(
        {
            "identifier": "dmap_id",
            "address": "127.0.0.1",
            "protocol": Protocol.DMAP.value,
            "name": "DMAP Device",
            "credentials": {Protocol.DMAP.value: "dummy_creds"},
        }
    )


async def test_user_adds_device_with_ip_filter(
    hass, flow, dmap_device_with_credentials
):
    """Test add device filtering by IP."""
    (await flow().step_user(identifier="127.0.0.1")).gives_form_confirm(
        description_placeholders={"name": "DMAP Device"}
    )

    (await flow().step_confirm()).gives_create_entry(
        {
            "identifier": "dmap_id",
            "address": "127.0.0.1",
            "protocol": Protocol.DMAP.value,
            "name": "DMAP Device",
            "credentials": {Protocol.DMAP.value: "dummy_creds"},
        }
    )


async def test_user_adds_device_by_ip_uses_unicast_scan(hass, flow, mock_scan):
    """Test add device by IP-address, verify unicast scan is used."""
    (await flow().step_user(identifier="127.0.0.1")).gives_form_user()

    assert str(mock_scan.hosts[0]) == "127.0.0.1"


async def test_user_adds_existing_device(hass, flow, mrp_device):
    """Test that it is not possible to add existing device."""
    MockConfigEntry(domain="apple_tv", data={"identifier": "mrp_id"}).add_to_hass(hass)

    (await flow().step_user(identifier="MRP Device")).gives_form_user(
        errors={"base": "device_already_configured"}
    )


async def test_user_adds_unusable_device(flow, airplay_device):
    """Test that it is not possible to add pure AirPlay device."""
    (await flow().step_user(identifier="AirPlay Device")).gives_form_user(
        errors={"base": "no_usable_service"}
    )


async def test_user_connection_failed(flow, mrp_device, pairing_mock):
    """Test error message when connection to device fails."""
    pairing_mock.begin.side_effect = exceptions.ConnectionFailedError()

    (await flow().step_user(identifier="MRP Device")).gives_form_confirm(
        description_placeholders={"name": "MRP Device"}
    )

    (await flow().step_confirm()).gives_form_service_problem(
        description_placeholders={"protocol": "MRP"}
    )

    (await flow().step_service_problem()).gives_abort("invalid_config")


async def test_user_start_pair_error_failed(flow, mrp_device, pairing_mock):
    """Test initiating pairing fails."""
    pairing_mock.begin.side_effect = exceptions.PairingError()

    (await flow().step_user(identifier="MRP Device")).gives_form_confirm(
        description_placeholders={"name": "MRP Device"}
    )

    (await flow().step_confirm()).gives_abort("auth")


async def test_user_pair_invalid_pin(flow, mrp_device, pairing_mock):
    """Test pairing with invalid pin."""
    pairing_mock.begin.return_value = mock_coro()
    pairing_mock.finish.side_effect = exceptions.PairingError()

    (await flow().step_user(identifier="MRP Device")).gives_form_confirm(
        description_placeholders={"name": "MRP Device"}
    )

    (await flow().step_confirm()).gives_form_pair_with_pin()

    (await flow().step_pair_with_pin(pin=1111)).gives_form_pair_with_pin(
        errors={"base": "auth"}
    )


async def test_user_pair_unexpected_error(flow, mrp_device, pairing_mock):
    """Test unexpected error when entering PIN code."""
    pairing_mock.begin.return_value = mock_coro()
    pairing_mock.finish.side_effect = Exception

    (await flow().step_user(identifier="MRP Device")).gives_form_confirm(
        description_placeholders={"name": "MRP Device"}
    )

    (await flow().step_confirm()).gives_form_pair_with_pin()

    (await flow().step_pair_with_pin(pin=1111)).gives_form_pair_with_pin(
        errors={"base": "unknown"}
    )


async def test_user_pair_backoff_error(flow, mrp_device, pairing_mock):
    """Test that backoff error is displayed in case device requests it."""
    pairing_mock.begin.side_effect = exceptions.BackOffError

    (await flow().step_user(identifier="MRP Device")).gives_form_confirm()

    (await flow().step_confirm()).gives_abort(reason="backoff")


async def test_user_pair_begin_unexpected_error(flow, mrp_device, pairing_mock):
    """Test unexpected error during start of pairing."""
    pairing_mock.begin.side_effect = Exception

    (await flow().step_user(identifier="MRP Device")).gives_form_confirm()

    (await flow().step_confirm()).gives_abort(reason="unrecoverable_error")


# Import Device


async def test_import_mrp_device(flow, mrp_device):
    """Test importing MRP device from YAML."""
    config = {
        "identifier": "mrp_id",
        "address": "127.0.0.1",
        "name": "Kitchen",
        "protocol": "MRP",
        "credentials": {"mrp": "mrp_creds"},
    }

    (await flow().step_import(**config)).gives_create_entry(
        {
            "identifier": "mrp_id",
            "address": "127.0.0.1",
            "protocol": Protocol.MRP.value,
            "name": "Kitchen",
            "credentials": {Protocol.MRP.value: "mrp_creds"},
        }
    )


# Zeroconf


async def test_zeroconf_unsupported_service_aborts(flow):
    """Test discovering unsupported zeroconf service."""
    service_info = {
        "type": "_dummy._tcp.local.",
        "properties": {},
    }

    (await flow().step_zeroconf(**service_info)).gives_abort("unrecoverable_error")


async def test_zeroconf_add_mrp_device(flow, mrp_device, pairing):
    """Test add MRP device discovered by zeroconf."""
    service_info = {
        "type": "_mediaremotetv._tcp.local.",
        "properties": {"UniqueIdentifier": "mrp_id", "Name": "Kitchen"},
    }

    (await flow().step_zeroconf(**service_info)).gives_form_confirm(
        description_placeholders={"name": "MRP Device"}
    )

    (await flow().step_confirm()).gives_form_pair_with_pin(
        description_placeholders={"protocol": "MRP"}
    )

    (await flow().step_pair_with_pin(pin=1234)).gives_create_entry(
        {
            "identifier": "mrp_id",
            "address": "127.0.0.1",
            "protocol": Protocol.MRP.value,
            "name": "MRP Device",
            "credentials": {Protocol.MRP.value: "mrp_creds"},
        }
    )


async def test_zeroconf_add_dmap_device(flow, dmap_device):
    """Test add DMAP device discovered by zeroconf."""
    service_info = {
        "type": "_touch-able._tcp.local.",
        "name": "dmap_id.something",
        "properties": {"CtlN": "Apple TV"},
    }

    (await flow().step_zeroconf(**service_info)).gives_form_confirm(
        description_placeholders={"name": "DMAP Device"}
    )


async def test_zeroconf_add_dmap_device_with_credentials(
    flow, dmap_device_with_credentials
):
    """Test add DMAP device with credentials discovered by zeroconf."""
    service_info = {
        "type": "_appletv-v2._tcp.local.",
        "name": "dmap_id.something",
        "properties": {"Name": "Apple TV"},
    }

    (await flow().step_zeroconf(**service_info)).gives_form_confirm(
        description_placeholders={"name": "DMAP Device"}
    )


async def test_zeroconf_add_existing_aborts(flow, dmap_device):
    """Test start new zeroconf flow while existing flow is active aborts."""
    service_info = {
        "type": "_touch-able._tcp.local.",
        "name": "dmap_id.something",
        "properties": {"CtlN": "Apple TV"},
    }

    (await flow().init_zeroconf(**service_info)).gives_form_confirm()
    (await flow().init_zeroconf(**service_info)).gives_abort("already_configured")


async def test_zeroconf_add_but_device_not_found(flow, mock_scan):
    """Test add device which is not found with another scan."""
    service_info = {
        "type": "_touch-able._tcp.local.",
        "name": "dmap_id.something",
        "properties": {"CtlN": "Apple TV"},
    }

    (await flow().step_zeroconf(**service_info)).gives_abort(reason="device_not_found")


async def test_zeroconf_add_existing_device(hass, flow, dmap_device):
    """Test add already existing device from zeroconf."""
    service_info = {
        "type": "_touch-able._tcp.local.",
        "name": "dmap_id.something",
        "properties": {"CtlN": "Apple TV"},
    }

    MockConfigEntry(domain="apple_tv", data={"identifier": "dmap_id"}).add_to_hass(hass)

    (await flow().step_zeroconf(**service_info)).gives_abort(
        reason="already_configured"
    )


async def test_zeroconf_unexpected_error(flow, mock_scan):
    """Test unexpected error aborts in zeroconf."""
    service_info = {
        "type": "_touch-able._tcp.local.",
        "name": "dmap_id.something",
        "properties": {"CtlN": "Apple TV"},
    }

    mock_scan.side_effect = Exception

    (await flow().step_zeroconf(**service_info)).gives_abort(
        reason="unrecoverable_error"
    )


# Re-configuration


async def test_reconfigure_ongoing_aborts(hass, flow, mrp_device):
    """Test start additional reconfigure flow aborts."""
    data = {
        "identifier": "mrp_id",
        "name": "Apple TV",
    }

    (await flow().init_invalid_credentials(**data)).gives_form_reconfigure()
    (await flow().init_invalid_credentials(**data)).gives_abort("already_configured")


async def test_reconfigure_update_credentials(hass, flow, mrp_device, pairing):
    """Test that reconfigure flow updates config entry."""
    config_entry = MockConfigEntry(domain="apple_tv", data={"identifier": "mrp_id"})
    config_entry.add_to_hass(hass)

    (
        await flow().step_invalid_credentials(identifier="mrp_id")
    ).gives_form_reconfigure()

    (await flow().step_reconfigure()).gives_form_pair_with_pin(
        description_placeholders={"protocol": "MRP"}
    )

    (await flow().step_pair_with_pin(pin=1234)).gives_abort("updated_configuration")

    assert config_entry.data == {
        "identifier": "mrp_id",
        "address": "127.0.0.1",
        "protocol": Protocol.MRP.value,
        "name": "MRP Device",
        "credentials": {Protocol.MRP.value: "mrp_creds"},
    }


# Options


async def test_option_start_off(options):
    """Test start off-option flag."""
    (await options().step_init()).gives_form_device_options()

    (await options().step_device_options(start_off=True)).gives_create_entry(
        {"start_off": True}
    )
