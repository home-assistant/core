"""Define tests for the The Things Network sensor."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration
from .conftest import (
    APP_ID,
    DATA_UPDATE,
    DEVICE_FIELD,
    DEVICE_FIELD_2,
    DEVICE_ID,
    DEVICE_ID_2,
    DOMAIN,
)


async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test a working configurations."""

    await init_integration(hass, mock_config_entry)

    # Check devices
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{APP_ID}_{DEVICE_ID}")}
        ).name
        == DEVICE_ID
    )

    # Check entities
    assert entity_registry.async_get(f"sensor.{DEVICE_ID}_{DEVICE_FIELD}")

    assert not entity_registry.async_get(f"sensor.{DEVICE_ID_2}_{DEVICE_FIELD}")
    push_callback = mock_ttnclient.call_args.kwargs["push_callback"]
    await push_callback(DATA_UPDATE)
    assert entity_registry.async_get(f"sensor.{DEVICE_ID_2}_{DEVICE_FIELD_2}")
