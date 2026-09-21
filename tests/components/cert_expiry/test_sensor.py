"""Tests for the Cert Expiry sensors."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cert_expiry.const import DOMAIN
from homeassistant.components.cert_expiry.errors import ResolveFailed, ValidationFailure
from homeassistant.components.cert_expiry.sensor import DIAGNOSTIC_DESCRIPTIONS
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms
from .const import HOST, PORT
from .helpers import certificate_expiring, future_timestamp, static_datetime

SENSOR_ENTITY_ID = "sensor.example_com_cert_expiry"


@pytest.mark.freeze_time(static_datetime())
@pytest.mark.usefixtures("cert_verified")
@pytest.mark.parametrize(
    ("port", "entity_id"),
    [
        pytest.param(PORT, SENSOR_ENTITY_ID, id="default_port"),
        pytest.param(
            8443, "sensor.example_com_8443_cert_expiry", id="non_default_port"
        ),
    ],
)
async def test_async_setup_entry(
    hass: HomeAssistant, port: int, entity_id: str
) -> None:
    """Test the timestamp sensor is created with the certificate's expiry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: port},
        unique_id=f"{HOST}:{port}",
    )
    timestamp = future_timestamp(100)
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(timestamp),
    ):
        await setup_with_selected_platforms(hass, entry, [Platform.SENSOR])

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid")
    assert entry.unique_id == f"{HOST}:{port}"


@pytest.mark.parametrize(
    "message",
    [
        pytest.param("some error", id="bad_cert"),
        pytest.param("No certificate found", id="empty_cert"),
    ],
)
async def test_async_setup_entry_validation_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, message: str
) -> None:
    """Test the sensor is unavailable when certificate validation fails during setup."""
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        side_effect=ValidationFailure(message),
    ):
        await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("cert_verified")
async def test_update_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor value survives a scheduled coordinator refresh."""
    freezer.move_to(static_datetime())
    timestamp = future_timestamp(100)
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(timestamp),
    ):
        await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == timestamp.isoformat()

    freezer.move_to(static_datetime() + timedelta(hours=24))
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(timestamp),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid")


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(ResolveFailed("cannot resolve"), id="resolve_failed"),
        pytest.param(ValidationFailure("something bad"), id="validation_failure"),
        pytest.param(Exception(), id="unexpected_exception"),
    ],
)
@pytest.mark.usefixtures("cert_verified", "mock_async_get_cert")
async def test_update_sensor_network_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test the sensor becomes unavailable when a scheduled refresh fails."""
    freezer.move_to(static_datetime())
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    freezer.move_to(static_datetime() + timedelta(hours=24))
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        side_effect=side_effect,
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("cert_verified")
async def test_update_sensor_recovers_after_network_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor recovers once a subsequent refresh succeeds."""
    timestamp = future_timestamp(100)

    freezer.move_to(static_datetime())
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(timestamp),
    ):
        await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == timestamp.isoformat()

    freezer.move_to(static_datetime() + timedelta(hours=24))
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        side_effect=ResolveFailed("cannot resolve"),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE

    freezer.move_to(static_datetime() + timedelta(hours=48))
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(timestamp),
    ):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == timestamp.isoformat()
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid")


@pytest.mark.usefixtures("cert_verified")
async def test_error_attribute_is_none_when_cert_valid(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the error attribute is None (not the string 'None') for a valid cert.

    Regression test: previously str(None) produced the misleading string "None"
    even when no error had occurred.
    """
    freezer.move_to(static_datetime())
    timestamp = future_timestamp(100)
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(timestamp),
    ):
        await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

        state = hass.states.get(SENSOR_ENTITY_ID)
        assert state.attributes.get("error") is None
        assert state.attributes.get("is_valid") is True

        freezer.move_to(static_datetime() + timedelta(hours=12))
        with patch(
            "homeassistant.components.cert_expiry.coordinator.HandshakePolicyVerifier.verify_cert",
            return_value="self-signed certificate",
        ):
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

        state = hass.states.get(SENSOR_ENTITY_ID)
        assert state.attributes.get("error") == "self-signed certificate"
        assert state.attributes.get("is_valid") is True

        freezer.move_to(static_datetime() + timedelta(hours=24))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state.attributes.get("error") is None
    assert state.attributes.get("is_valid") is True


@pytest.mark.freeze_time(static_datetime())
@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_async_get_cert", "cert_verified"
)
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation and values of the sensors."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time(static_datetime())
@pytest.mark.usefixtures("mock_async_get_cert", "cert_verified")
async def test_only_expiry_sensor_enabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the certificate metadata sensors are disabled by default."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert sorted(entry.entity_id for entry in entries if not entry.disabled) == [
        SENSOR_ENTITY_ID
    ]
    assert len(entries) == 1 + len(DIAGNOSTIC_DESCRIPTIONS)
