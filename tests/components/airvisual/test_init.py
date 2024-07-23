"""Define tests for AirVisual init."""

from unittest.mock import patch

from homeassistant.components.airvisual import (
    CONF_CITY,
    CONF_GEOGRAPHIES,
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    INTEGRATION_TYPE_GEOGRAPHY_NAME,
    INTEGRATION_TYPE_NODE_PRO,
)
from homeassistant.components.airvisual_pro import DOMAIN as AIRVISUAL_PRO_DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_IP_ADDRESS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_STATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .conftest import (
    COORDS_CONFIG,
    COORDS_CONFIG2,
    NAME_CONFIG,
    TEST_API_KEY,
    TEST_CITY,
    TEST_COUNTRY,
    TEST_LATITUDE,
    TEST_LATITUDE2,
    TEST_LONGITUDE,
    TEST_LONGITUDE2,
    TEST_STATE,
)

from tests.common import MockConfigEntry


async def test_migration_1_2(hass: HomeAssistant, mock_pyairvisual) -> None:
    """Test migrating from version 1 to 2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_API_KEY,
        data={
            CONF_API_KEY: TEST_API_KEY,
            CONF_GEOGRAPHIES: [
                {
                    CONF_LATITUDE: TEST_LATITUDE,
                    CONF_LONGITUDE: TEST_LONGITUDE,
                },
                {
                    CONF_CITY: TEST_CITY,
                    CONF_STATE: TEST_STATE,
                    CONF_COUNTRY: TEST_COUNTRY,
                },
                {
                    CONF_LATITUDE: TEST_LATITUDE2,
                    CONF_LONGITUDE: TEST_LONGITUDE2,
                },
            ],
        },
        version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 3

    # Ensure that after migration, each configuration has its own config entry:
    identifier1 = f"{TEST_LATITUDE}, {TEST_LONGITUDE}"
    assert config_entries[0].unique_id == identifier1
    assert config_entries[0].title == f"Cloud API ({identifier1})"
    assert config_entries[0].data == {
        **COORDS_CONFIG,
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    }

    identifier2 = f"{TEST_CITY}, {TEST_STATE}, {TEST_COUNTRY}"
    assert config_entries[1].unique_id == identifier2
    assert config_entries[1].title == f"Cloud API ({identifier2})"
    assert config_entries[1].data == {
        **NAME_CONFIG,
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY_NAME,
    }

    identifier3 = f"{TEST_LATITUDE2}, {TEST_LONGITUDE2}"
    assert config_entries[2].unique_id == identifier3
    assert config_entries[2].title == f"Cloud API ({identifier3})"
    assert config_entries[2].data == {
        **COORDS_CONFIG2,
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    }


async def test_migration_2_3(
    hass: HomeAssistant, mock_pyairvisual, device_registry: dr.DeviceRegistry
) -> None:
    """Test migrating from version 2 to 3."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.100",
        data={
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "abcde12345",
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_NODE_PRO,
        },
        version=2,
    )
    entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        name="192.168.1.100",
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "SERIAL_NUMBER")},
    )

    with patch(
        "homeassistant.components.airvisual.automation.automations_with_device",
        return_value=["automation.test_automation"],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Ensure that after migration, the AirVisual Pro device has been moved to the
        # `airvisual_pro` domain and an issue has been created:
        for domain, entry_count in ((DOMAIN, 0), (AIRVISUAL_PRO_DOMAIN, 1)):
            assert len(hass.config_entries.async_entries(domain)) == entry_count

        issue_registry = ir.async_get(hass)
        assert len(issue_registry.issues) == 1
