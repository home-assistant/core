"""The tests for the Picnic sensor platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from python_picnic_api2.models import DeliverySummary, Eta
import requests
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.picnic.const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.picnic.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_setup_platform_not_available(
    hass: HomeAssistant,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the set-up of the sensor platform if API is not available."""
    mock_picnic_api.get_user.side_effect = requests.exceptions.ConnectionError
    mock_picnic_api.get_cart.side_effect = requests.exceptions.ConnectionError
    mock_picnic_api.get_deliveries.side_effect = requests.exceptions.ConnectionError
    mock_picnic_api.get_delivery_position.side_effect = (
        requests.exceptions.ConnectionError
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get("sensor.mock_title_max_order_time_of_selected_slot") is None
    assert hass.states.get("sensor.mock_title_status_of_last_order") is None
    assert hass.states.get("sensor.mock_title_total_price_of_last_order") is None


async def test_sensors_no_selected_time_slot(
    hass: HomeAssistant,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor states with no explicit selected time slot."""
    cart = mock_picnic_api.get_cart.return_value
    cart.selected_slot.state = "IMPLICIT"

    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.mock_title_start_of_selected_slot").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get("sensor.mock_title_end_of_selected_slot").state == STATE_UNKNOWN
    )
    assert (
        hass.states.get("sensor.mock_title_max_order_time_of_selected_slot").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get("sensor.mock_title_minimum_order_value_for_selected_slot").state
        == STATE_UNKNOWN
    )


async def test_next_delivery_sensors(
    hass: HomeAssistant,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor states when last order is not yet delivered."""
    delivery = mock_picnic_api.get_deliveries.return_value[0]
    delivery.raw["delivery_time"] = None
    delivery.status = "CURRENT"

    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.mock_title_last_order_delivery_time").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get("sensor.mock_title_expected_start_of_next_delivery").state
        == "2021-02-26T19:54:00+00:00"
    )
    assert (
        hass.states.get("sensor.mock_title_expected_end_of_next_delivery").state
        == "2021-02-26T20:14:00+00:00"
    )
    assert (
        hass.states.get("sensor.mock_title_start_of_next_delivery_s_slot").state
        == "2021-02-26T19:15:00+00:00"
    )
    assert (
        hass.states.get("sensor.mock_title_end_of_next_delivery_s_slot").state
        == "2021-02-26T20:15:00+00:00"
    )


async def test_sensors_eta_date_malformed(
    hass: HomeAssistant,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor states when last order eta dates are malformed."""
    await setup_integration(hass, mock_config_entry)

    delivery = mock_picnic_api.get_deliveries.return_value[0]
    delivery.eta2 = Eta(start="wrong-time", end="other-malformed-datetime")
    delivery.status = "CURRENT"

    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        hass.states.get("sensor.mock_title_expected_start_of_next_delivery").state
        == STATE_UNKNOWN
    )
    assert (
        hass.states.get("sensor.mock_title_expected_end_of_next_delivery").state
        == STATE_UNKNOWN
    )


async def test_sensors_use_detailed_eta_if_available(
    hass: HomeAssistant,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor states use the more precise delivery position ETA."""
    await setup_integration(hass, mock_config_entry)

    delivery = mock_picnic_api.get_deliveries.return_value[0]
    delivery.raw["delivery_time"] = None
    delivery.status = "CURRENT"
    mock_picnic_api.get_delivery_position.return_value = {
        "eta_window": {
            "start": "2021-03-05T10:19:20.452+00:00",
            "end": "2021-03-05T10:39:20.452+00:00",
        },
        "eta": 1614941090000,
    }

    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_picnic_api.get_delivery_position.assert_called_with(delivery.delivery_id)
    assert (
        hass.states.get("sensor.mock_title_expected_start_of_next_delivery").state
        == "2021-03-05T10:19:20+00:00"
    )
    assert (
        hass.states.get("sensor.mock_title_expected_end_of_next_delivery").state
        == "2021-03-05T10:39:20+00:00"
    )
    assert (
        hass.states.get("sensor.mock_title_estimated_arrival_of_next_delivery").state
        == "2021-03-05T10:44:50+00:00"
    )


async def test_sensors_no_data(
    hass: HomeAssistant,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor states when the api only returns empty objects."""
    await setup_integration(hass, mock_config_entry)

    mock_picnic_api.get_user.return_value = {}
    mock_picnic_api.get_cart.return_value = None
    mock_picnic_api.get_deliveries.return_value = None
    mock_picnic_api.get_delivery_position.side_effect = ValueError

    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id in (
        "sensor.mock_title_cart_total_price",
        "sensor.mock_title_start_of_selected_slot",
        "sensor.mock_title_end_of_selected_slot",
        "sensor.mock_title_max_order_time_of_selected_slot",
        "sensor.mock_title_minimum_order_value_for_selected_slot",
        "sensor.mock_title_max_order_time_of_last_order",
        "sensor.mock_title_last_order_delivery_time",
        "sensor.mock_title_expected_start_of_next_delivery",
        "sensor.mock_title_expected_end_of_next_delivery",
    ):
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_sensors_malformed_delivery_data(
    hass: HomeAssistant,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor states when the delivery api returns not a list."""
    await setup_integration(hass, mock_config_entry)

    mock_picnic_api.get_deliveries.return_value = {"error": "message"}

    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id in (
        "sensor.mock_title_max_order_time_of_last_order",
        "sensor.mock_title_last_order_delivery_time",
        "sensor.mock_title_expected_start_of_next_delivery",
        "sensor.mock_title_expected_end_of_next_delivery",
    ):
        assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_sensors_malformed_response(
    hass: HomeAssistant,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors become unavailable when the API yields ValueError."""
    await setup_integration(hass, mock_config_entry)

    mock_picnic_api.get_user.side_effect = ValueError
    mock_picnic_api.get_cart.side_effect = ValueError

    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        hass.states.get("sensor.mock_title_cart_total_price").state == STATE_UNAVAILABLE
    )


async def test_multiple_active_orders(
    hass: HomeAssistant,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor values with multiple active orders."""
    completed = mock_picnic_api.get_deliveries.return_value[0]

    def _undelivered(window_start: str, window_end: str, eta_start: str, eta_end: str):
        order = DeliverySummary.from_api(completed.raw.copy())
        order.raw["delivery_time"] = None
        order.status = "CURRENT"
        order.slot.window_start = window_start
        order.slot.window_end = window_end
        order.eta2 = Eta(start=eta_start, end=eta_end)
        return order

    undelivered_order = _undelivered(
        "2022-03-01T09:15:00.000+01:00",
        "2022-03-01T10:15:00.000+01:00",
        "2022-03-01T09:30:00.000+01:00",
        "2022-03-01T09:45:00.000+01:00",
    )
    undelivered_order_2 = _undelivered(
        "2022-03-08T13:15:00.000+01:00",
        "2022-03-08T14:15:00.000+01:00",
        "2022-03-08T13:30:00.000+01:00",
        "2022-03-08T13:45:00.000+01:00",
    )

    mock_picnic_api.get_deliveries.return_value = [
        undelivered_order_2,
        undelivered_order,
        completed,
    ]
    mock_picnic_api.get_delivery_position.return_value = {}

    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.mock_title_start_of_last_order_s_slot").state
        == "2022-03-08T12:15:00+00:00"
    )
    assert (
        hass.states.get("sensor.mock_title_end_of_last_order_s_slot").state
        == "2022-03-08T13:15:00+00:00"
    )
    assert (
        hass.states.get("sensor.mock_title_start_of_next_delivery_s_slot").state
        == "2022-03-01T08:15:00+00:00"
    )
    assert (
        hass.states.get("sensor.mock_title_end_of_next_delivery_s_slot").state
        == "2022-03-01T09:15:00+00:00"
    )
    assert (
        hass.states.get("sensor.mock_title_expected_start_of_next_delivery").state
        == "2022-03-01T08:30:00+00:00"
    )
    assert (
        hass.states.get("sensor.mock_title_expected_end_of_next_delivery").state
        == "2022-03-01T08:45:00+00:00"
    )


async def test_device_registry_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if device registry entry is populated correctly."""
    await setup_integration(hass, mock_config_entry)

    picnic_service = device_registry.async_get_device_by_identifier(
        (DOMAIN, "295-6y3-1nf4"),
        mock_config_entry.entry_id,
    )
    assert picnic_service.model == "295-6y3-1nf4"
    assert picnic_service.name == "Mock Title"
    assert picnic_service.entry_type is dr.DeviceEntryType.SERVICE


async def test_auth_token_is_saved_on_update(
    hass: HomeAssistant,
    mock_picnic_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test auth-token changes are reflected by the config entry."""
    await setup_integration(hass, mock_config_entry)

    updated_auth_token = "x-updated-picnic-auth-token"
    mock_picnic_api.session.auth_token = updated_auth_token

    assert mock_config_entry.data.get(CONF_ACCESS_TOKEN) != updated_auth_token

    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.data.get(CONF_ACCESS_TOKEN) == updated_auth_token
