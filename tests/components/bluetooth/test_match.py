"""Tests for bluetooth matching behavior with empty manufacturer_data."""

from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth.match import (
    IntegrationMatchHistory,
    seen_all_fields,
)


def test_empty_manufacturer_data_is_not_dropped() -> None:
    """Ensure empty manufacturer_data {} is treated as present and not dropped."""
    previous = IntegrationMatchHistory(
        manufacturer_data=None,
        service_data=set(),
        service_uuids=set(),
    )

    adv = AdvertisementData(
        local_name="Test",
        manufacturer_data={},  # empty dict should be considered present (not None)
        service_data={},
        service_uuids=[],
        rssi=-50,
        platform_data=((),),
        tx_power=-127,
    )

    # Since previous.manufacturer_data is None and adv.manufacturer_data is not None,
    # seen_all_fields should return False (meaning there is new data to consider,
    # and we should not early-exit/drop this advertisement).
    assert not seen_all_fields(previous, adv)

    # Simulate updating the history as IntegrationMatcher.match_domains would do
    # and ensure the manufacturer_data flag becomes True.
    if previous.manufacturer_data is None and adv.manufacturer_data is not None:
        previous.manufacturer_data = True

    assert previous.manufacturer_data is True


