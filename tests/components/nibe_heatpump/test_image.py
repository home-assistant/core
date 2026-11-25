"""Test the Nibe Heat Pump heating curve images."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from nibe.coil_groups import HEATING_CURVE_COILGROUPS
from nibe.heatpump import Model
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.image import SVGImageSnapshotExtension
from syrupy.location import PyTestLocation

from homeassistant.components.image import async_get_image
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from . import MockConnection, async_add_model


class SVGSnapshotExtension(SVGImageSnapshotExtension):
    """Store SVG snapshots in the snapshots folder, like the amber snapshots."""

    @classmethod
    def dirname(cls, *, test_location: PyTestLocation) -> str:
        """Return the directory for the snapshot files."""
        test_dir = Path(test_location.filepath).parent
        return str(test_dir.joinpath("snapshots", test_location.basename))


@pytest.fixture(autouse=True)
async def fixture_single_platform():
    """Only allow this platform to load."""
    with patch("homeassistant.components.nibe_heatpump.PLATFORMS", [Platform.IMAGE]):
        yield


def _setup_heating_curve(
    coils: dict[int, Any], model: Model, values: dict[str, Any]
) -> None:
    group = HEATING_CURVE_COILGROUPS[model.series]["s1"]
    for field, value in values.items():
        coils[getattr(group, field)] = value


BASE_VALUES = {
    "curve": 10,
    "offset": 1,
    "min_supply": 20.0,
    "max_supply": 65.0,
    "room_setpoint": 20.5,
    "room_factor": 3.0,
    "room_temperature": 20.7,
    "calculated_supply": 38.1,
    "outdoor_temperature": 6.3,
    "supply_temperature": 36.4,
    "return_temperature": 31.2,
}


@pytest.mark.parametrize(
    ("model", "entity_id", "values"),
    [
        pytest.param(
            Model.F1155,
            "image.f1155_heating_curve_s1",
            {**BASE_VALUES, "use_room_sensor": "OFF"},
            id="f_series",
        ),
        pytest.param(
            Model.F1155,
            "image.f1155_heating_curve_s1",
            {**BASE_VALUES, "use_room_sensor": "ON"},
            id="f_series_room_sensor",
        ),
        pytest.param(
            Model.S1155,
            "image.s1155_heating_curve_s1",
            {**BASE_VALUES, "use_room_sensor": 0},
            id="s_series",
        ),
        pytest.param(
            Model.F1155,
            "image.f1155_heating_curve_s1",
            {
                "curve": 15,
                "min_supply": 20.0,
                "max_supply": 80.0,
                "outdoor_temperature": -45.0,
                "calculated_supply": 80.0,
            },
            id="clamped_without_optional_coils",
        ),
        pytest.param(
            Model.F1155,
            "image.f1155_heating_curve_s1",
            {**BASE_VALUES, "use_room_sensor": "OFF", "calculated_supply": None},
            id="outdoor_only",
        ),
        pytest.param(
            Model.F1155,
            "image.f1155_heating_curve_s1",
            {**BASE_VALUES, "use_room_sensor": "OFF", "outdoor_temperature": None},
            id="supply_only",
        ),
    ],
)
async def test_image(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    coils: dict[int, Any],
    model: Model,
    entity_id: str,
    values: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the rendered heating curve."""
    _setup_heating_curve(coils, model, values)

    await async_add_model(hass, model)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    image = await async_get_image(hass, entity_id)
    assert image.content_type == "image/svg+xml"
    assert image.content.decode() == snapshot(extension_class=SVGSnapshotExtension)


async def test_update(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    coils: dict[int, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the image follows the curve settings."""
    entity_id = "image.f1155_heating_curve_s1"
    group = HEATING_CURVE_COILGROUPS[Model.F1155.series]["s1"]
    _setup_heating_curve(coils, Model.F1155, BASE_VALUES)

    await async_add_model(hass, Model.F1155)

    state = hass.states.get(entity_id)
    assert state is not None
    first_updated = state.state
    first_image = (await async_get_image(hass, entity_id)).content

    freezer.tick(60)
    with patch(
        "homeassistant.components.nibe_heatpump.image.HeatingCurveCoilGroupData.svg"
    ) as mock_svg:
        mock_connection.mock_coil_update(group.curve, BASE_VALUES["curve"])
    mock_svg.assert_not_called()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == first_updated

    mock_connection.mock_coil_update(group.curve, 5)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != first_updated
    assert (await async_get_image(hass, entity_id)).content != first_image

    mock_connection.mock_coil_update(group.curve, 0)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_disabled_by_default(
    hass: HomeAssistant,
    coils: dict[int, Any],
) -> None:
    """Test systems that need an accessory are disabled by default."""
    for key in ("s1", "s2"):
        group = HEATING_CURVE_COILGROUPS[Model.F1155.series][key]
        coils[group.curve] = 10
        coils[group.min_supply] = 20.0
        coils[group.max_supply] = 65.0

    await async_add_model(hass, Model.F1155)

    assert hass.states.get("image.f1155_heating_curve_s1") is not None
    assert hass.states.get("image.f1155_heating_curve_s2") is None
