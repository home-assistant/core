"""Test the Home Assistant Green config flow."""
from unittest.mock import patch

import pytest

from homeassistant.components.hassio import DOMAIN as HASSIO_DOMAIN
from homeassistant.components.homeassistant_green.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration


@pytest.fixture(name="get_green_settings")
def mock_get_green_settings():
    """Mock getting green settings."""
    with patch(
        "homeassistant.components.homeassistant_green.config_flow.async_get_green_settings",
        return_value={
            "activity_led": True,
            "power_led": True,
            "system_health_led": True,
        },
    ) as get_green_settings:
        yield get_green_settings


@pytest.fixture(name="set_green_settings")
def mock_set_green_settings():
    """Mock setting green settings."""
    with patch(
        "homeassistant.components.homeassistant_green.config_flow.async_set_green_settings",
    ) as set_green_settings:
        yield set_green_settings


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    with patch(
        "homeassistant.components.homeassistant_green.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant Green"
    assert result["data"] == {}
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {}
    assert config_entry.title == "Home Assistant Green"


async def test_config_flow_single_entry(hass: HomeAssistant) -> None:
    """Test only a single entry is allowed."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Green",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_green.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    mock_setup_entry.assert_not_called()


async def test_option_flow_non_hassio(
    hass: HomeAssistant,
) -> None:
    """Test installing the multi pan addon on a Core installation, without hassio."""
    mock_integration(hass, MockModule("hassio"))

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Green",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_green.config_flow.is_hassio",
        return_value=False,
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_hassio"


async def test_option_flow_led_settings(
    hass: HomeAssistant,
    get_green_settings,
    set_green_settings,
) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Green",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "hardware_settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"activity_led": False, "power_led": False, "system_health_led": False},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    set_green_settings.assert_called_once_with(
        hass, {"activity_led": False, "power_led": False, "system_health_led": False}
    )


async def test_option_flow_led_settings_unchanged(
    hass: HomeAssistant,
    get_green_settings,
    set_green_settings,
) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Green",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "hardware_settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"activity_led": True, "power_led": True, "system_health_led": True},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    set_green_settings.assert_not_called()


async def test_option_flow_led_settings_fail_1(hass: HomeAssistant) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Green",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_green.config_flow.async_get_green_settings",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "read_hw_settings_error"


async def test_option_flow_led_settings_fail_2(
    hass: HomeAssistant, get_green_settings
) -> None:
    """Test updating LED settings."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Green",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "hardware_settings"

    with patch(
        "homeassistant.components.homeassistant_green.config_flow.async_set_green_settings",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"activity_led": False, "power_led": False, "system_health_led": False},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "write_hw_settings_error"
