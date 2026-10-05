"""Test ViCare sensor entity."""

from contextlib import ExitStack
from datetime import timedelta
import threading
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from PyViCare.PyViCareService import ViCareDeviceAccessor
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.vicare.const import DEFAULT_CACHE_DURATION
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json"),
        Fixture({"type:heatpump"}, "vicare/Vitocal250A.json"),
        Fixture({"type:heatpump"}, "vicare/Vitocal222G_Vitovent300W.json"),
        Fixture({"type:ventilation"}, "vicare/ViAir300F.json"),
        Fixture({"type:ventilation"}, "vicare/VitoPure.json"),
        Fixture({"type:ess"}, "vicare/VitoChargeVX3.json"),
        Fixture({None}, "vicare/VitoValor.json"),
        Fixture({"type:climateSensor"}, "vicare/RoomSensor1.json"),
        Fixture({"type:climateSensor"}, "vicare/RoomSensor2.json"),
        Fixture({"type:radiator"}, "vicare/ZigbeeTRV.json"),
        Fixture({"type:repeater"}, "vicare/ZigbeeRepeater.json"),
        # FHT main and channel are the same physical zigbee node, so they share
        # a gateway; this lets the channel link to the main via via_device.
        Fixture({"type:fhtMain"}, "vicare/FHTMain.json", gateway_id="fht_gateway"),
        Fixture(
            {"type:fhtChannel"}, "vicare/FHTChannel.json", gateway_id="fht_gateway"
        ),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_api_read_on_event_loop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entity values must be read in the executor, never on the event loop.

    A PyViCare getter takes the library's cache lock and does blocking I/O when
    that cache is cold, so reading a value from a property freezes the loop for
    the length of an HTTP request.
    """
    fixtures: list[Fixture] = [
        Fixture({"type:heatpump"}, "vicare/Vitocal250A.json"),
        Fixture({"type:ventilation"}, "vicare/VitoPure.json"),
    ]
    mock_vicare = MockPyViCare(fixtures)
    services = {id(d.service): d.service for d in mock_vicare.devices}

    loop_thread_id = threading.get_ident()
    reads_on_loop: list[str] = []
    reads_in_executor: list[str] = []

    def guard(service):
        read_property = service.getProperty

        def guarded_get_property(
            accessor: ViCareDeviceAccessor, property_name: str
        ) -> Any:
            if threading.get_ident() == loop_thread_id:
                reads_on_loop.append(property_name)
            else:
                reads_in_executor.append(property_name)
            return read_property(accessor, property_name)

        return patch.object(service, "getProperty", guarded_get_property)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=mock_vicare.as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.SENSOR, Platform.FAN]),
    ):
        await setup_integration(hass, mock_config_entry)

        entity_ids = hass.states.async_entity_ids(SENSOR_DOMAIN)
        fan_ids = hass.states.async_entity_ids(FAN_DOMAIN)
        assert entity_ids
        assert fan_ids

        with ExitStack() as stack:
            for service in services.values():
                stack.enter_context(guard(service))

            freezer.tick(timedelta(seconds=DEFAULT_CACHE_DURATION * 2))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

            for entity_id in (entity_ids[0], fan_ids[0]):
                await async_update_entity(hass, entity_id)

    assert not reads_on_loop
    # Without this the test would also pass if nothing read a value at all.
    assert reads_in_executor
