"""Tests for the Cert Expiry sensors."""

from datetime import timedelta
import socket
import ssl
from unittest.mock import ANY, patch

from cryptography import x509
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.cert_expiry.const import CONF_CA_CERTIFICATES, DOMAIN
from homeassistant.components.cert_expiry.errors import ValidationFailure
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_VERIFY_SSL,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.util.dt import utcnow
from homeassistant.util.ssl import SSL_ALPN_HTTP11, create_client_context

from .const import HOST, PORT
from .helpers import future_timestamp, static_datetime


@pytest.mark.freeze_time(static_datetime())
async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    timestamp = future_timestamp(100)

    with patch(
        "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
        return_value=timestamp,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid")


@pytest.mark.parametrize(
    ("tls_options", "is_valid"),
    [
        pytest.param({}, True, id="legacy-entry"),
        pytest.param({CONF_VERIFY_SSL: True}, True, id="verified"),
        pytest.param({CONF_VERIFY_SSL: False}, False, id="unverified"),
    ],
)
async def test_certificate_verification_status(
    hass: HomeAssistant,
    certificate: x509.Certificate,
    certificate_der: bytes,
    tls_options: dict[str, bool],
    is_valid: bool,
) -> None:
    """Only claim validity when certificate verification was enabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT, **tls_options},
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        return_value=certificate_der,
    ) as get_cert:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    get_cert.assert_awaited_with(hass, HOST, PORT, verify_ssl=is_valid, ssl_context=ANY)
    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state == certificate.not_valid_after_utc.isoformat()
    assert state.attributes["is_valid"] is is_valid
    assert state.attributes["error"] is None


@pytest.mark.freeze_time(static_datetime())
async def test_validation_error_changes(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Publish a new validation error when both polls have an unknown expiry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
        side_effect=ValidationFailure("untrusted issuer"),
    ) as get_timestamp:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.example_com_cert_expiry")
        assert state is not None
        assert state.attributes["error"] == "untrusted issuer"

        get_timestamp.side_effect = ValidationFailure("certificate has expired")
        freezer.tick(timedelta(hours=12))
        async_fire_time_changed(hass, utcnow())
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["is_valid"] is False
    assert state.attributes["error"] == "certificate has expired"


@pytest.mark.freeze_time(static_datetime())
async def test_custom_ca_context_reused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    certificate_pem: str,
) -> None:
    """Build an entry's custom context once and reuse it across scheduled polls."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_CA_CERTIFICATES: certificate_pem,
        },
        unique_id=f"{HOST}:{PORT}",
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.cert_expiry.helper.create_client_context",
            wraps=create_client_context,
        ) as create_context,
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=future_timestamp(100),
        ) as get_timestamp,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        context = get_timestamp.await_args.kwargs["ssl_context"]

        freezer.tick(timedelta(hours=12))
        async_fire_time_changed(hass, utcnow())
        await hass.async_block_till_done()

    create_context.assert_called_once_with(alpn_protocols=SSL_ALPN_HTTP11)
    get_timestamp.assert_awaited_with(
        hass, HOST, PORT, verify_ssl=True, ssl_context=context
    )


async def test_async_setup_entry_bad_cert(hass: HomeAssistant) -> None:
    """Test async_setup_entry with a bad/expired cert."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        side_effect=ssl.SSLError("some error"),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes.get("error") == "some error"
    assert not state.attributes.get("is_valid")


async def test_update_sensor(hass: HomeAssistant) -> None:
    """Test async_update for sensor."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    starting_time = static_datetime()
    timestamp = future_timestamp(100)

    with (
        freeze_time(starting_time),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=24)
    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=24))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid")


async def test_update_sensor_network_errors(hass: HomeAssistant) -> None:
    """Test async_update for sensor."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    starting_time = static_datetime()
    timestamp = future_timestamp(100)

    with (
        freeze_time(starting_time),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=24)

    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.helper.async_get_cert",
            side_effect=socket.gaierror,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=24))
        await hass.async_block_till_done()

    next_update = starting_time + timedelta(hours=48)

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.state == STATE_UNAVAILABLE

    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=48))
        await hass.async_block_till_done()

        state = hass.states.get("sensor.example_com_cert_expiry")
        assert state is not None
        assert state.state != STATE_UNAVAILABLE
        assert state.state == timestamp.isoformat()
        assert state.attributes.get("error") is None
        assert state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=72)

    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.helper.async_get_cert",
            side_effect=ssl.SSLError("something bad"),
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=72))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("error") == "something bad"
    assert not state.attributes.get("is_valid")

    next_update = starting_time + timedelta(hours=96)

    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.helper.async_get_cert",
            side_effect=Exception(),
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=96))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.state == STATE_UNAVAILABLE


async def test_error_attribute_is_none_when_cert_valid(hass: HomeAssistant) -> None:
    """Test that the error attribute is None (not the string 'None') for a valid cert.

    Regression test: previously str(None) produced the misleading string "None"
    even when no error had occurred.
    """
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    starting_time = static_datetime()
    timestamp = future_timestamp(100)

    # Start with a valid cert — error should be None, not "None"
    with (
        freeze_time(starting_time),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid") is True

    # Simulate a cert error on next poll
    next_update = starting_time + timedelta(hours=12)
    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.helper.async_get_cert",
            side_effect=ssl.SSLError("certificate has expired"),
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=12))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.attributes.get("error") == "certificate has expired"
    assert state.attributes.get("is_valid") is False

    # Cert becomes valid again — error must return to None, not "None"
    next_update = starting_time + timedelta(hours=24)
    with (
        freeze_time(next_update),
        patch(
            "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
            return_value=timestamp,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=24))
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid") is True


async def test_async_setup_entry_empty_cert(hass: HomeAssistant) -> None:
    """Test setup when peer certificate is empty (e.g. verify_mode=CERT_NONE)."""
    assert hass.state is CoreState.running

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )

    with patch(
        "homeassistant.components.cert_expiry.helper.async_get_cert",
        return_value=None,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_cert_expiry")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes.get("error") is not None
    assert not state.attributes.get("is_valid")


async def test_non_default_port(hass: HomeAssistant) -> None:
    """Test sensor naming and unique_id when a non-default port is used."""
    assert hass.state is CoreState.running

    non_default_port = 8443
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: non_default_port},
        unique_id=f"{HOST}:{non_default_port}",
    )

    timestamp = future_timestamp(100)

    with patch(
        "homeassistant.components.cert_expiry.coordinator.get_cert_expiry_timestamp",
        return_value=timestamp,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.example_com_8443_cert_expiry")
    assert state is not None
    assert state.state == timestamp.isoformat()
    assert entry.unique_id == f"{HOST}:{non_default_port}"
