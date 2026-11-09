"""The tests for the geolocation component."""

import pytest
from pytest_homeassistant.common import (
    import_and_test_deprecated_constant,
    import_and_test_deprecated_constant_enum,
)

from homeassistant.components import geo_location
from homeassistant.components.geo_location import (
    GeolocationEntityStateAttribute,
    GeolocationEvent,
)
from homeassistant.const import EntityStateAttribute
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup_component(hass: HomeAssistant) -> None:
    """Simple test setup of component."""
    result = await async_setup_component(hass, geo_location.DOMAIN, {})
    assert result


async def test_event(hass: HomeAssistant) -> None:
    """Simple test of the geolocation event class."""
    entity = GeolocationEvent()

    assert entity.state is None
    assert entity.distance is None
    assert entity.latitude is None
    assert entity.longitude is None
    with pytest.raises(AttributeError):
        assert entity.source is None


@pytest.mark.parametrize(
    "replacement",
    [
        EntityStateAttribute.LATITUDE,
        EntityStateAttribute.LONGITUDE,
        GeolocationEntityStateAttribute.SOURCE,
    ],
)
def test_deprecated_constant_enum(
    caplog: pytest.LogCaptureFixture,
    replacement: EntityStateAttribute | GeolocationEntityStateAttribute,
) -> None:
    """Test the deprecated constants replaced by enums."""
    import_and_test_deprecated_constant_enum(
        caplog, geo_location, replacement, "ATTR_", "2027.12"
    )


def test_deprecated_attr_distance(caplog: pytest.LogCaptureFixture) -> None:
    """Test the deprecated ATTR_DISTANCE constant, which has no replacement."""
    import_and_test_deprecated_constant(
        caplog, geo_location, "ATTR_DISTANCE", None, "distance", "2027.12"
    )
