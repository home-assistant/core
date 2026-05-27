"""BleBox base entity tests."""

import logging
from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi
import pytest

from homeassistant.components.switch import DATA_COMPONENT
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import async_setup_entities, mock_only_feature, setup_product_mock


@pytest.fixture(name="switchbox_d_entity")
def switchbox_d_entity_fixture():
    """Return two Switch feature mocks sharing a switchBoxD product."""

    def relay_mock(relay_id):
        return mock_only_feature(
            blebox_uniapi.switch.Switch,
            unique_id=f"BleBox-switchBoxD-1afe34e750b8-{relay_id}.relay",
            full_name=f"switchBoxD-{relay_id}.relay",
            device_class="relay",
            is_on=None,
        )

    relay1 = relay_mock(0)
    relay2 = relay_mock(1)
    features = [relay1, relay2]

    product = setup_product_mock("switches", features)
    type(product).name = PropertyMock(return_value="My relays")
    type(product).model = PropertyMock(return_value="switchBoxD")
    type(product).brand = PropertyMock(return_value="BleBox")
    type(product).firmware_version = PropertyMock(return_value="1.23")
    type(product).unique_id = PropertyMock(return_value="abcd0123ef5678")

    type(relay1).product = product
    type(relay2).product = product

    return (
        features,
        ["switch.my_relays_switchboxd_0_relay", "switch.my_relays_switchboxd_1_relay"],
    )


async def test_update_failure(
    hass: HomeAssistant,
    switchbox_d_entity: tuple[list[AsyncMock], list[str]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that first update failure marks entity unavailable and logs at info level."""

    caplog.set_level(logging.INFO)

    feature_mocks, entity_ids = switchbox_d_entity
    feature_mocks[0].async_update = AsyncMock(
        side_effect=blebox_uniapi.error.ClientError
    )
    feature_mocks[1].async_update = AsyncMock(
        side_effect=blebox_uniapi.error.ClientError
    )
    await async_setup_entities(hass, entity_ids)

    assert f"Updating '{feature_mocks[0].full_name}' failed: " in caplog.text
    assert hass.states.get(entity_ids[0]).state == STATE_UNAVAILABLE
    assert hass.states.get(entity_ids[1]).state == STATE_UNAVAILABLE


async def test_update_failure_not_repeated(
    hass: HomeAssistant,
    switchbox_d_entity: tuple[list[AsyncMock], list[str]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that repeated update failures do not log additional messages."""

    caplog.set_level(logging.INFO)

    feature_mocks, entity_ids = switchbox_d_entity
    feature_mocks[0].async_update = AsyncMock(
        side_effect=blebox_uniapi.error.ClientError
    )
    feature_mocks[1].async_update = AsyncMock(
        side_effect=blebox_uniapi.error.ClientError
    )
    await async_setup_entities(hass, entity_ids)

    assert f"Updating '{feature_mocks[0].full_name}' failed: " in caplog.text
    record_count = len(caplog.records)

    entity = hass.data[DATA_COMPONENT].get_entity(entity_ids[0])
    await entity.async_update_ha_state(force_refresh=True)

    assert len(caplog.records) == record_count
    assert hass.states.get(entity_ids[0]).state == STATE_UNAVAILABLE


async def test_update_failure_then_recovery(
    hass: HomeAssistant,
    switchbox_d_entity: tuple[list[AsyncMock], list[str]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that entity becomes available again after a successful update."""

    caplog.set_level(logging.INFO)

    feature_mocks, entity_ids = switchbox_d_entity
    feature_mocks[0].async_update = AsyncMock(
        side_effect=blebox_uniapi.error.ClientError
    )
    feature_mocks[1].async_update = AsyncMock(
        side_effect=blebox_uniapi.error.ClientError
    )
    await async_setup_entities(hass, entity_ids)

    assert hass.states.get(entity_ids[0]).state == STATE_UNAVAILABLE

    feature_mocks[0].async_update = AsyncMock()
    feature_mocks[0].is_on = True
    entity = hass.data[DATA_COMPONENT].get_entity(entity_ids[0])
    await entity.async_update_ha_state(force_refresh=True)

    assert hass.states.get(entity_ids[0]).state == STATE_ON
    assert f"'{feature_mocks[0].full_name}' is back online" in caplog.text
