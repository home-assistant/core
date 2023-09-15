"""Tests for the Aprilaire base entity."""

import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.aprilaire.coordinator import AprilaireCoordinator
from homeassistant.components.aprilaire.entity import BaseAprilaireEntity
from homeassistant.helpers.entity import DeviceInfo


@pytest.fixture
def logger() -> logging.Logger:
    """Return a logger."""
    logger = logging.getLogger()
    logger.propagate = False

    return logger


@pytest.fixture
def coordinator(logger: logging.Logger) -> AprilaireCoordinator:
    """Return a mock coordinator."""

    coordinator_mock = AsyncMock(AprilaireCoordinator)
    coordinator_mock.data = {}
    coordinator_mock.logger = logger

    return coordinator_mock


async def test_available_on_init(coordinator: AprilaireCoordinator) -> None:
    """Test that the entity becomes available on init."""

    update_available_mock = Mock()
    with patch(
        "homeassistant.components.aprilaire.entity.BaseAprilaireEntity._update_available",
        new=update_available_mock,
    ):
        BaseAprilaireEntity(coordinator)
    update_available_mock.assert_called_once()


async def test_handle_coordinator_update(coordinator: AprilaireCoordinator) -> None:
    """Test that the coordinator updates the entity."""

    update_available_mock = Mock()
    async_write_ha_state_mock = Mock()

    with patch(
        "homeassistant.components.aprilaire.entity.BaseAprilaireEntity._update_available",
        new=update_available_mock,
    ), patch(
        "homeassistant.helpers.entity.Entity.async_write_ha_state",
        new=async_write_ha_state_mock,
    ):
        entity = BaseAprilaireEntity(coordinator)
        entity._handle_coordinator_update()

    update_available_mock.assert_called_once()
    async_write_ha_state_mock.assert_called_once()


async def test_update_available_stopped(coordinator: AprilaireCoordinator) -> None:
    """Test that the stopped state causes the entity to not be available."""

    entity = BaseAprilaireEntity(coordinator)

    coordinator.data["stopped"] = True
    entity._update_available()

    assert entity._attr_available is False
    assert entity.available is False


async def test_update_available_no_mac(coordinator: AprilaireCoordinator) -> None:
    """Test that no MAC address causes the entity to not be available."""

    entity = BaseAprilaireEntity(coordinator)

    coordinator.data["connected"] = True
    coordinator.data["stopped"] = False
    coordinator.data["mac_address"] = None
    entity._update_available()

    assert entity._attr_available is False
    assert entity.available is False


async def test_update_available_connected_not_stopped(
    coordinator: AprilaireCoordinator,
) -> None:
    """Test that the connected state causes the entity to be available."""

    entity = BaseAprilaireEntity(coordinator)

    coordinator.data["connected"] = True
    coordinator.data["stopped"] = False
    coordinator.data["mac_address"] = "1:2:3:4:5:6"
    entity._update_available()

    assert entity._attr_available is True
    assert entity.available is True


async def test_update_available_reconnecting_not_stopped(
    coordinator: AprilaireCoordinator,
) -> None:
    """Test that the entity remains available when reconnecting."""

    entity = BaseAprilaireEntity(coordinator)

    coordinator.data["connected"] = False
    coordinator.data["reconnecting"] = True
    coordinator.data["stopped"] = False
    coordinator.data["mac_address"] = "1:2:3:4:5:6"
    entity._update_available()

    assert entity._attr_available is True
    assert entity.available is True


def test_should_poll(coordinator: AprilaireCoordinator) -> None:
    """Test that the entity does not poll."""

    entity = BaseAprilaireEntity(coordinator)

    assert entity.should_poll is False


def test_unique_id(coordinator: AprilaireCoordinator) -> None:
    """Test the generation of the entity's unique ID."""

    entity = BaseAprilaireEntity(coordinator)

    coordinator.data["mac_address"] = "1:2:3:4:5:6"

    with patch(
        "homeassistant.components.aprilaire.entity.BaseAprilaireEntity.name",
        new="Test Entity",
    ):
        assert entity.unique_id == "1_2_3_4_5_6_test_entity"


def test_extra_state_attributes(coordinator: AprilaireCoordinator) -> None:
    """Test the entity's extra state attributes."""

    entity = BaseAprilaireEntity(coordinator)
    coordinator.data["location"] = "Test Location"

    assert entity.extra_state_attributes == {
        "device_location": "Test Location",
    }


def test_device_info(coordinator: AprilaireCoordinator) -> None:
    """Test the device info."""

    coordinator.device_info = DeviceInfo()

    entity = BaseAprilaireEntity(coordinator)
    device_info = entity.device_info

    assert device_info == coordinator.device_info
