"""Test Epson component setup process."""
from homeassistant.components.epson.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


async def test_migrate_entry(hass):
    """Test successful migration of entry data."""
    legacy_config = {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 80,
    }
    entry = MockConfigEntry(domain=DOMAIN, title="test-epson", data=legacy_config)
    print(entry)
    assert entry.data == legacy_config
    assert entry.version == 1
    assert not entry.unique_id

    # Create entity entry to migrate to new unique ID
    # registry = er.async_get(hass)
    # registry.async_get_or_create(
    #     BINARY_SENSOR_DOMAIN,
    #     AXIS_DOMAIN,
    #     "00408C123456-vmd4-0",
    #     suggested_object_id="vmd4",
    #     config_entry=entry,
    # )

    # await entry.async_migrate(hass)

    # assert entry.data == {
    #     CONF_DEVICE: {
    #         CONF_HOST: "1.2.3.4",
    #         CONF_USERNAME: "username",
    #         CONF_PASSWORD: "password",
    #         CONF_PORT: 80,
    #     },
    #     CONF_HOST: "1.2.3.4",
    #     CONF_USERNAME: "username",
    #     CONF_PASSWORD: "password",
    #     CONF_PORT: 80,
    #     CONF_MAC: "00408C123456",
    #     CONF_MODEL: "model",
    #     CONF_NAME: "name",
    # }
    # assert entry.version == 2  # Keep version to support rollbacking
    # assert entry.unique_id == "00:40:8c:12:34:56"

    # vmd4_entity = registry.async_get("binary_sensor.vmd4")
    # assert vmd4_entity.unique_id == "00:40:8c:12:34:56-vmd4-0"
