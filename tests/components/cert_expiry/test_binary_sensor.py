"""Tests for the Cert Expiry binary sensors."""

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cert_expiry.errors import ValidationFailure
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms
from .helpers import certificate_expiring, future_timestamp, static_datetime

ENTITIES = (
    "binary_sensor.example_com_problem",
    "binary_sensor.example_com_certificate_invalid",
    "binary_sensor.example_com_certificate_untrusted",
    "binary_sensor.example_com_tls_version_unsupported",
    "binary_sensor.example_com_cipher_unsupported",
)
INVALID = ENTITIES[1]

EXPIRES = future_timestamp(100)


@pytest.mark.freeze_time(static_datetime())
@pytest.mark.usefixtures("mock_async_get_cert", "cert_verified")
async def test_binary_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation and values of the binary sensors."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.BINARY_SENSOR]
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    (
        "now",
        "cert_error",
        "tls_version_error",
        "cipher_error",
        "expected_states",
        "expected_reason",
    ),
    [
        pytest.param(
            static_datetime(),
            None,
            None,
            None,
            (STATE_OFF, STATE_OFF, STATE_OFF, STATE_OFF, STATE_OFF),
            None,
            id="healthy",
        ),
        pytest.param(
            static_datetime(),
            "self-signed",
            None,
            None,
            (STATE_ON, STATE_OFF, STATE_ON, STATE_OFF, STATE_OFF),
            None,
            id="untrusted_but_in_validity_period",
        ),
        pytest.param(
            EXPIRES + timedelta(days=1),
            "not valid at validation time",
            None,
            None,
            (STATE_ON, STATE_ON, STATE_ON, STATE_OFF, STATE_OFF),
            "expired",
            id="expired_is_also_untrusted",
        ),
        pytest.param(
            datetime(2005, 1, 1, tzinfo=static_datetime().tzinfo),
            None,
            None,
            None,
            (STATE_ON, STATE_ON, STATE_OFF, STATE_OFF, STATE_OFF),
            "not_yet_valid",
            id="not_yet_valid",
        ),
        pytest.param(
            static_datetime(),
            None,
            "below the minimum",
            None,
            (STATE_ON, STATE_OFF, STATE_OFF, STATE_ON, STATE_OFF),
            None,
            id="tls_version",
        ),
        pytest.param(
            static_datetime(),
            None,
            None,
            "not enabled",
            (STATE_ON, STATE_OFF, STATE_OFF, STATE_OFF, STATE_ON),
            None,
            id="cipher",
        ),
        pytest.param(
            static_datetime(),
            "self-signed",
            "below the minimum",
            "not enabled",
            (STATE_ON, STATE_OFF, STATE_ON, STATE_ON, STATE_ON),
            None,
            id="every_check_fails",
        ),
    ],
)
@pytest.mark.usefixtures("mock_async_get_cert")
async def test_states(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    now: datetime,
    cert_error: str | None,
    tls_version_error: str | None,
    cipher_error: str | None,
    expected_states: tuple[str, ...],
    expected_reason: str | None,
) -> None:
    """Test each check reports independently and several can fire at once."""
    freezer.move_to(now)

    with (
        patch(
            "homeassistant.components.cert_expiry.coordinator.HandshakePolicyVerifier.verify_cert",
            return_value=cert_error,
        ),
        patch(
            "homeassistant.components.cert_expiry.coordinator.HandshakePolicyVerifier.verify_tls_version",
            return_value=tls_version_error,
        ),
        patch(
            "homeassistant.components.cert_expiry.coordinator.HandshakePolicyVerifier.verify_cipher",
            return_value=cipher_error,
        ),
    ):
        await setup_with_selected_platforms(
            hass, mock_config_entry, [Platform.BINARY_SENSOR]
        )

    assert tuple(hass.states.get(entity).state for entity in ENTITIES) == (
        expected_states
    )
    assert hass.states.get(INVALID).attributes["reason"] == expected_reason


@pytest.mark.freeze_time(static_datetime())
async def test_unavailable_when_handshake_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test every binary sensor is unavailable when the handshake fails."""
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        side_effect=ValidationFailure("no certificate"),
    ):
        await setup_with_selected_platforms(
            hass, mock_config_entry, [Platform.BINARY_SENSOR]
        )

    assert [hass.states.get(entity).state for entity in ENTITIES] == [
        STATE_UNAVAILABLE
    ] * len(ENTITIES)


@pytest.mark.freeze_time(static_datetime())
async def test_untrusted_certificate_from_real_verification(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the self-signed test certificate fails the real chain verification."""
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(EXPIRES),
    ):
        await setup_with_selected_platforms(
            hass, mock_config_entry, [Platform.BINARY_SENSOR]
        )

    assert hass.states.get("binary_sensor.example_com_certificate_untrusted").state == (
        STATE_ON
    )
    assert hass.states.get(INVALID).state == STATE_OFF
