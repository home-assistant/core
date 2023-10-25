"""Test the Random config flow."""
from typing import Any
from unittest.mock import patch

import pytest
from voluptuous import Invalid

from homeassistant import config_entries
from homeassistant.components.random import async_setup_entry
from homeassistant.components.random.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    (
        "entity_type",
        "extra_input",
        "extra_options",
    ),
    (
        (
            "binary_sensor",
            {},
            {},
        ),
        (
            "sensor",
            {
                "device_class": SensorDeviceClass.POWER,
                "unit_of_measurement": UnitOfPower.WATT,
            },
            {
                "device_class": SensorDeviceClass.POWER,
                "unit_of_measurement": UnitOfPower.WATT,
                "minimum": 0,
                "maximum": 20,
            },
        ),
        (
            "sensor",
            {},
            {"minimum": 0, "maximum": 20},
        ),
    ),
)
async def test_config_flow(
    hass: HomeAssistant,
    entity_type: str,
    extra_input: dict[str, Any],
    extra_options: dict[str, Any],
) -> None:
    """Test the config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": entity_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == entity_type

    with patch(
        "homeassistant.components.random.async_setup_entry", wraps=async_setup_entry
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My random entity",
                **extra_input,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My random entity"
    assert result["data"] == {}
    assert result["options"] == {
        "name": "My random entity",
        "entity_type": entity_type,
        **extra_options,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("device_class", "unit_of_measurement"),
    [
        (SensorDeviceClass.POWER, UnitOfEnergy.WATT_HOUR),
        (SensorDeviceClass.ILLUMINANCE, UnitOfEnergy.WATT_HOUR),
    ],
)
async def test_wrong_uom(
    hass: HomeAssistant, device_class: SensorDeviceClass, unit_of_measurement: str
) -> None:
    """Test entering a wrong unit of measurement."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "sensor"},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "sensor"

    with pytest.raises(Invalid, match="is not a valid unit for device class"):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My random entity",
                "device_class": device_class,
                "unit_of_measurement": unit_of_measurement,
            },
        )


@pytest.mark.parametrize(
    (
        "entity_type",
        "extra_options",
        "options_options",
    ),
    (
        (
            "sensor",
            {
                "device_class": SensorDeviceClass.ENERGY,
                "unit_of_measurement": UnitOfEnergy.WATT_HOUR,
                "minimum": 0,
                "maximum": 20,
            },
            {
                "minimum": 10,
                "maximum": 20,
                "device_class": SensorDeviceClass.POWER,
                "unit_of_measurement": UnitOfPower.WATT,
            },
        ),
    ),
)
async def test_options(
    hass: HomeAssistant,
    entity_type: str,
    extra_options,
    options_options,
) -> None:
    """Test reconfiguring."""

    random_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My random",
            "entity_type": entity_type,
            **extra_options,
        },
        title="My random",
    )
    random_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(random_config_entry.entry_id)
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == entity_type
    assert "name" not in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=options_options,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "My random",
        "entity_type": entity_type,
        **options_options,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My random",
        "entity_type": entity_type,
        **options_options,
    }
    assert config_entry.title == "My random"
