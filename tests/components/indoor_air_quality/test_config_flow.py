"""Test the Indoor Air Quality config flow."""

from homeassistant import config_entries
from homeassistant.components.indoor_air_quality.config_flow import (
    CONF_SHOW_SOURCE_OPTIONS,
)
from homeassistant.components.indoor_air_quality.const import (
    CONF_HCHO,
    CONF_HUMIDITY,
    CONF_PM,
    CONF_SOURCES,
    CONF_STANDARD,
    CONF_TEMPERATURE,
    CONF_TVOC,
    CONF_VOC_INDEX,
    DOMAIN,
    STANDARD_UK,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


def _create_mock_device(hass: HomeAssistant, device_name: str = "VINDSTYRKA") -> str:
    """Create a mock source device."""
    config_entry = MockConfigEntry(domain="zha")
    config_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("zha", device_name.lower())},
        manufacturer="IKEA of Sweden",
        name=device_name,
    )

    return device_entry.id


def _create_mock_sensor(
    hass: HomeAssistant,
    device_id: str,
    suggested_object_id: str,
    device_class: SensorDeviceClass | None = None,
    original_name: str | None = None,
) -> None:
    """Create a mock source sensor for a device."""
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "sensor",
        "zha",
        suggested_object_id,
        suggested_object_id=suggested_object_id,
        device_id=device_id,
        original_device_class=device_class,
        original_name=original_name,
    )


async def test_form_user(hass: HomeAssistant) -> None:
    """Test manual source setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SHOW_SOURCE_OPTIONS: True},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "sources"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_NAME: "Test Air Quality",
            CONF_TEMPERATURE: "sensor.temperature",
            CONF_HUMIDITY: "sensor.humidity",
        },
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Test Air Quality"
    assert result3["data"] == {
        CONF_SOURCES: {
            CONF_TEMPERATURE: "sensor.temperature",
            CONF_HUMIDITY: "sensor.humidity",
        },
        CONF_STANDARD: STANDARD_UK,
    }


async def test_form_user_no_sources(hass: HomeAssistant) -> None:
    """Test user form with no device and no sources errors out."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "device_or_sources"}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SHOW_SOURCE_OPTIONS: True},
    )
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {CONF_NAME: "Test Air Quality"},
    )

    assert result4["type"] is FlowResultType.FORM
    assert result4["step_id"] == "sources"
    assert result4["errors"] == {"base": "no_sources"}


async def test_form_user_both_voc_sensors(hass: HomeAssistant) -> None:
    """Test user form rejects both VOC sources at once."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SHOW_SOURCE_OPTIONS: True},
    )

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_NAME: "Test Air Quality",
            CONF_TVOC: "sensor.tvoc",
            CONF_VOC_INDEX: "sensor.voc_index",
        },
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "sources"
    assert result3["errors"] == {"base": "only_one_voc_sensor"}


async def test_form_user_device_sources(hass: HomeAssistant) -> None:
    """Test user form auto-detects sources from a selected device."""
    device_id = _create_mock_device(hass)
    _create_mock_sensor(
        hass, device_id, "kitchen_temperature", SensorDeviceClass.TEMPERATURE
    )
    _create_mock_sensor(hass, device_id, "kitchen_humidity", SensorDeviceClass.HUMIDITY)
    _create_mock_sensor(hass, device_id, "kitchen_pm25", SensorDeviceClass.PM25)
    _create_mock_sensor(hass, device_id, "kitchen_voc_index", original_name="VOC index")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_ID: device_id},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "VINDSTYRKA"
    assert result2["data"] == {
        CONF_DEVICE_ID: device_id,
        CONF_SOURCES: {
            CONF_TEMPERATURE: "sensor.kitchen_temperature",
            CONF_HUMIDITY: "sensor.kitchen_humidity",
            CONF_PM: ["sensor.kitchen_pm25"],
            CONF_VOC_INDEX: "sensor.kitchen_voc_index",
        },
        CONF_STANDARD: STANDARD_UK,
    }


async def test_form_user_device_extra_sources(hass: HomeAssistant) -> None:
    """Test user form merges manual sources with device-detected sources."""
    device_id = _create_mock_device(hass, "Kitchen Monitor")
    _create_mock_sensor(
        hass, device_id, "kitchen_temperature", SensorDeviceClass.TEMPERATURE
    )
    _create_mock_sensor(hass, device_id, "kitchen_humidity", SensorDeviceClass.HUMIDITY)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_ID: device_id,
            CONF_SHOW_SOURCE_OPTIONS: True,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "sources"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_HCHO: "sensor.kitchen_formaldehyde"},
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Kitchen Monitor"
    assert result3["data"] == {
        CONF_DEVICE_ID: device_id,
        CONF_SOURCES: {
            CONF_TEMPERATURE: "sensor.kitchen_temperature",
            CONF_HUMIDITY: "sensor.kitchen_humidity",
            CONF_HCHO: "sensor.kitchen_formaldehyde",
        },
        CONF_STANDARD: STANDARD_UK,
    }


async def test_form_user_device_no_matching_sources(hass: HomeAssistant) -> None:
    """Test user form errors when a device has no supported sensors."""
    device_id = _create_mock_device(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_ID: device_id},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "no_matching_sources"}


async def test_form_user_already_configured(hass: HomeAssistant) -> None:
    """Test user form aborts when an entry with the same name already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    sources_step = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SHOW_SOURCE_OPTIONS: True},
    )
    await hass.config_entries.flow.async_configure(
        sources_step["flow_id"],
        {
            CONF_NAME: "Test Air Quality",
            CONF_TEMPERATURE: "sensor.temperature",
        },
    )
    await hass.async_block_till_done()

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_SHOW_SOURCE_OPTIONS: True},
    )
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {
            CONF_NAME: "Test Air Quality",
            CONF_TEMPERATURE: "sensor.temperature",
        },
    )

    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test the options flow returns its form and persists changes."""
    hass.states.async_set("sensor.test", 20, {"unit_of_measurement": "°C"})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOURCES: {CONF_TEMPERATURE: "sensor.test"},
            CONF_STANDARD: STANDARD_UK,
        },
        title="Test",
        unique_id="test",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_TEMPERATURE: "sensor.new_temperature",
            CONF_HUMIDITY: "sensor.new_humidity",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data[CONF_SOURCES] == {
        CONF_TEMPERATURE: "sensor.new_temperature",
        CONF_HUMIDITY: "sensor.new_humidity",
    }
    assert config_entry.data[CONF_STANDARD] == STANDARD_UK


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test the reconfigure flow updates and reloads the entry."""
    hass.states.async_set("sensor.test", "20", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.new_temp", "21", {"unit_of_measurement": "°C"})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SOURCES: {CONF_TEMPERATURE: "sensor.test"},
            CONF_STANDARD: STANDARD_UK,
        },
        title="Test",
        unique_id="test",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TEMPERATURE: "sensor.new_temp"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_SOURCES] == {CONF_TEMPERATURE: "sensor.new_temp"}
