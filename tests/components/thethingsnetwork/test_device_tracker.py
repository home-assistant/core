"""Define tests for the The Things Network sensor."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration
from .conftest import (
    APP_ID,
    DATA_UPDATE,
    DEVICE_ID,
    DEVICE_ID_2,
    DOMAIN,
    TRACKER_FIELD,
    TRACKER_FIELD_2,
)


async def test_device_tracker(
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
    assert (
        entity_registry.async_get(f"device_tracker.{DEVICE_ID}_{TRACKER_FIELD}").domain
        == Platform.DEVICE_TRACKER
    )

    assert not entity_registry.async_get(
        f"device_tracker.{DEVICE_ID_2}_{TRACKER_FIELD_2}"
    )
    push_callback = mock_ttnclient.call_args.kwargs["push_callback"]
    await push_callback(DATA_UPDATE)
    assert (
        entity_registry.async_get(
            f"device_tracker.{DEVICE_ID_2}_{TRACKER_FIELD_2}"
        ).domain
        == Platform.DEVICE_TRACKER
    )
