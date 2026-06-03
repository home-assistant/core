"""BleBox update entity tests."""

from datetime import timedelta
from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi.error
import blebox_uniapi.update
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateDeviceClass,
    UpdateEntityFeature,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import async_setup_entity, mock_feature

from tests.common import async_fire_time_changed


@pytest.fixture(name="firmwareupdate")
def firmwareupdate_fixture() -> tuple[blebox_uniapi.update.Update, str]:
    """Return a firmware update mock for airSensor."""
    feature = mock_feature(
        "updates",
        blebox_uniapi.update.Update,
        unique_id="BleBox-airSensor-4a3fdaad90aa-firmware",
        full_name="airSensor-firmware",
        installed_version="0.1",
        latest_version="0.2",
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My airSensor")
    type(product).model = PropertyMock(return_value="airSensor")
    return (feature, "update.my_airsensor_airsensor_firmware")


async def test_init(
    firmwareupdate: tuple[blebox_uniapi.update.Update, str],
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test firmware update entity default state after setup."""
    _, entity_id = firmwareupdate
    entry = await async_setup_entity(hass, entity_id)

    assert entry.unique_id == "BleBox-airSensor-4a3fdaad90aa-firmware"

    state = hass.states.get(entity_id)
    assert state.name == "My airSensor airSensor-firmware"
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE

    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_features & UpdateEntityFeature.INSTALL
    assert supported_features & UpdateEntityFeature.PROGRESS

    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.1"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.state == STATE_ON

    device = device_registry.async_get(entry.device_id)
    assert device.name == "My airSensor"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "airSensor"


async def test_update(
    firmwareupdate: tuple[blebox_uniapi.update.Update, str],
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that async_update refreshes versions and syncs sw_version to device registry."""
    feature_mock, entity_id = firmwareupdate

    def initial_update() -> None:
        feature_mock.installed_version = "0.1"
        feature_mock.latest_version = "0.2"

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    entry = await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.1"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.2"

    def second_update() -> None:
        feature_mock.installed_version = "0.2"
        feature_mock.latest_version = "0.2"

    feature_mock.async_update = AsyncMock(side_effect=second_update)
    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.2"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.2"
    assert state.state == STATE_OFF

    device = device_registry.async_get(entry.device_id)
    assert device.sw_version == "0.2"


async def test_update_error(
    firmwareupdate: tuple[blebox_uniapi.update.Update, str],
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a failed async_update raises HomeAssistantError."""
    feature_mock, entity_id = firmwareupdate
    await async_setup_entity(hass, entity_id)

    feature_mock.async_update = AsyncMock(
        side_effect=blebox_uniapi.error.ClientError("connection refused")
    )
    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()

    assert "HomeAssistantError" in caplog.text


@pytest.mark.freeze_time("2026-05-21 00:00:00")
async def test_install(
    firmwareupdate: tuple[blebox_uniapi.update.Update, str],
    hass: HomeAssistant,
) -> None:
    """Test that async_install triggers feature install and sets in_progress."""
    feature_mock, entity_id = firmwareupdate

    def initial_update() -> None:
        feature_mock.installed_version = "0.1"
        feature_mock.latest_version = "0.2"

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_IN_PROGRESS] is False

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    feature_mock.async_install.assert_awaited_once()

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.1"


async def test_install_error(
    firmwareupdate: tuple[blebox_uniapi.update.Update, str],
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an install failure clears in_progress and raises HomeAssistantError."""
    feature_mock, entity_id = firmwareupdate

    def initial_update() -> None:
        feature_mock.installed_version = "0.1"
        feature_mock.latest_version = "0.2"

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    feature_mock.async_install = AsyncMock(
        side_effect=blebox_uniapi.error.ClientError("install failed")
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_IN_PROGRESS] is False

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    feature_mock.async_update.assert_called_once()


@pytest.mark.freeze_time("2026-05-21 00:00:00")
async def test_poll_until_updated_success(
    firmwareupdate: tuple[blebox_uniapi.update.Update, str],
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the poll timer resolves in_progress once the version changes."""
    feature_mock, entity_id = firmwareupdate

    def initial_update() -> None:
        feature_mock.installed_version = "0.1"
        feature_mock.latest_version = "0.2"

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    entry = await async_setup_entity(hass, entity_id)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).attributes[ATTR_IN_PROGRESS] is True

    def poll_update() -> None:
        feature_mock.installed_version = "0.2"

    feature_mock.async_update = AsyncMock(side_effect=poll_update)

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.2"
    assert state.state == STATE_OFF

    device = device_registry.async_get(entry.device_id)
    assert device.sw_version == "0.2"


@pytest.mark.freeze_time("2026-05-21 00:00:00")
async def test_poll_connection_error(
    firmwareupdate: tuple[blebox_uniapi.update.Update, str],
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that ConnectionError during poll reschedules the next poll without updating sw_version."""
    feature_mock, entity_id = firmwareupdate

    def initial_update() -> None:
        feature_mock.installed_version = "0.1"
        feature_mock.latest_version = "0.2"

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    entry = await async_setup_entity(hass, entity_id)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).attributes[ATTR_IN_PROGRESS] is True

    feature_mock.async_update = AsyncMock(
        side_effect=blebox_uniapi.error.ConnectionError
    )

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_IN_PROGRESS] is True

    device = device_registry.async_get(entry.device_id)
    assert device.sw_version == "0.1"

    def recovery_update() -> None:
        feature_mock.installed_version = "0.2"

    feature_mock.async_update = AsyncMock(side_effect=recovery_update)

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.freeze_time("2026-05-21 00:00:00")
async def test_poll_max_attempts(
    firmwareupdate: tuple[blebox_uniapi.update.Update, str],
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that in_progress is cleared after _MAX_POLL_ATTEMPTS polls."""
    feature_mock, entity_id = firmwareupdate

    def initial_update() -> None:
        feature_mock.installed_version = "0.1"
        feature_mock.latest_version = "0.2"

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).attributes[ATTR_IN_PROGRESS] is True

    feature_mock.async_update = AsyncMock(
        side_effect=blebox_uniapi.error.ConnectionError
    )

    for _ in range(29):
        freezer.tick(timedelta(seconds=11))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes[ATTR_IN_PROGRESS] is True

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.freeze_time("2026-05-21 00:00:00")
async def test_poll_other_error(
    firmwareupdate: tuple[blebox_uniapi.update.Update, str],
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a non-connection Error during poll cancels in_progress immediately."""
    feature_mock, entity_id = firmwareupdate

    def initial_update() -> None:
        feature_mock.installed_version = "0.1"
        feature_mock.latest_version = "0.2"

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).attributes[ATTR_IN_PROGRESS] is True

    feature_mock.async_update = AsyncMock(
        side_effect=blebox_uniapi.error.HttpError("500", "server error")
    )

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.freeze_time("2026-05-21 00:00:00")
async def test_remove_cancels_poll(
    firmwareupdate: tuple[blebox_uniapi.update.Update, str],
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that removing the entity cancels the pending poll timer."""
    feature_mock, entity_id = firmwareupdate

    def initial_update() -> None:
        feature_mock.installed_version = "0.1"
        feature_mock.latest_version = "0.2"

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, entity_id)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).attributes[ATTR_IN_PROGRESS] is True

    registry_entry = entity_registry.async_get(entity_id)
    config_entry = hass.config_entries.async_get_entry(registry_entry.config_entry_id)

    call_count_before = feature_mock.async_update.await_count
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert feature_mock.async_update.await_count == call_count_before
