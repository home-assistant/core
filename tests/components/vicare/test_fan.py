"""Test ViCare fan."""

from unittest.mock import patch

import pytest
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.const import ATTR_ICON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [
        Fixture({"type:ventilation"}, "vicare/ViAir300F.json"),
        Fixture({"type:ventilation"}, "vicare/VitoPure.json"),
        Fixture({"type:heatpump"}, "vicare/Vitocal222G_Vitovent300W.json"),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.FAN]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_standby_quickmode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the fan follows the standby quickmode.

    The value is now read in the executor and cached, so a read that stops
    being supported must not leave the fan reported as in standby. The recorded
    level of this device is unknown, which is why the icon and not the state
    carries the difference here.
    """
    fixtures: list[Fixture] = [Fixture({"type:ventilation"}, "vicare/VitoPure.json")]
    vicare_data = MockPyViCare(fixtures).as_vicare_data()
    api = vicare_data.devices[0].api

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}._setup_vicare_api", return_value=vicare_data),
        patch(f"{MODULE}.PLATFORMS", [Platform.FAN]),
    ):
        await setup_integration(hass, mock_config_entry)

        entity_id = hass.states.async_entity_ids(FAN_DOMAIN)[0]
        assert "standby" in hass.states.get(entity_id).attributes["vicare_quickmodes"]

        # The fixture runs sensor driven and reports the quickmode as inactive.
        await async_update_entity(hass, entity_id)
        assert hass.states.get(entity_id).attributes[ATTR_ICON] == "mdi:fan-auto"

        with patch.object(api, "getVentilationQuickmode", return_value=True):
            await async_update_entity(hass, entity_id)
        assert hass.states.get(entity_id).attributes[ATTR_ICON] == "mdi:fan-off"

        with patch.object(
            api,
            "getVentilationQuickmode",
            side_effect=PyViCareNotSupportedFeatureError("standby"),
        ):
            await async_update_entity(hass, entity_id)
        assert hass.states.get(entity_id).attributes[ATTR_ICON] == "mdi:fan-auto"
