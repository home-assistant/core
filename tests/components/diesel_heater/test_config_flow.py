"""Tests for Diesel Heater config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.diesel_heater.const import (
    CONF_PRESET_AWAY_TEMP,
    CONF_PRESET_COMFORT_TEMP,
    DEFAULT_PIN,
    DEFAULT_PRESET_AWAY_TEMP,
    DEFAULT_PRESET_COMFORT_TEMP,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    DIESEL_HEATER_MFR_ID_ONLY,
    DIESEL_HEATER_NAME_ONLY,
    DIESEL_HEATER_SERVICE_INFO,
    NOT_DIESEL_HEATER_SERVICE_INFO,
    TEST_ADDRESS,
)

from tests.common import MockConfigEntry


async def test_bluetooth_discovery_shows_confirm(hass: HomeAssistant) -> None:
    """Bluetooth discovery proceeds to the confirm step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DIESEL_HEATER_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """Bluetooth discovery aborts when the device is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_PIN: DEFAULT_PIN},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DIESEL_HEATER_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_confirm_creates_entry_with_default_pin(hass: HomeAssistant) -> None:
    """Confirm step creates an entry with the default PIN."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DIESEL_HEATER_SERVICE_INFO,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == TEST_ADDRESS
    assert result["data"][CONF_PIN] == DEFAULT_PIN


async def test_confirm_creates_entry_with_custom_pin(hass: HomeAssistant) -> None:
    """Confirm step creates an entry with a custom PIN."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=DIESEL_HEATER_SERVICE_INFO,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PIN: 5678}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PIN] == 5678


async def test_user_step_no_devices_redirects_to_manual(hass: HomeAssistant) -> None:
    """User step redirects to manual entry when no devices are discovered."""
    with patch(
        "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ".async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_user_step_detects_device(hass: HomeAssistant) -> None:
    """User step lists discovered diesel heaters."""
    with patch(
        "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ".async_discovered_service_info",
        return_value=[DIESEL_HEATER_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_creates_entry(hass: HomeAssistant) -> None:
    """Selecting a device from the user step creates an entry."""
    with patch(
        "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ".async_discovered_service_info",
        return_value=[DIESEL_HEATER_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: TEST_ADDRESS, CONF_PIN: DEFAULT_PIN},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == TEST_ADDRESS


async def test_user_step_detects_device_by_name_only(hass: HomeAssistant) -> None:
    """User step matches a device by name even without service UUID or mfr id."""
    with patch(
        "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ".async_discovered_service_info",
        return_value=[DIESEL_HEATER_NAME_ONLY],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_detects_device_by_manufacturer_id_only(
    hass: HomeAssistant,
) -> None:
    """User step matches a device by manufacturer id 0xFFFF alone."""
    with patch(
        "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ".async_discovered_service_info",
        return_value=[DIESEL_HEATER_MFR_ID_ONLY],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_skips_already_configured_device(hass: HomeAssistant) -> None:
    """User step skips devices already configured in another entry."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_PIN: DEFAULT_PIN},
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ".async_discovered_service_info",
        return_value=[DIESEL_HEATER_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    # The only discovered device is already configured -> no devices visible,
    # flow falls through to the manual step.
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_user_step_aborts_when_creating_duplicate_entry(
    hass: HomeAssistant,
) -> None:
    """Creating an entry for an already-configured address aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_PIN: DEFAULT_PIN},
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ".async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: TEST_ADDRESS, CONF_PIN: DEFAULT_PIN},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_step_ignores_unknown_devices(hass: HomeAssistant) -> None:
    """User step does not show devices that are not diesel heaters."""
    with patch(
        "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ".async_discovered_service_info",
        return_value=[NOT_DIESEL_HEATER_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_manual_creates_entry_valid_mac(hass: HomeAssistant) -> None:
    """Manual MAC entry with valid format creates an entry."""
    with patch(
        "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ".async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: TEST_ADDRESS, CONF_PIN: DEFAULT_PIN},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == TEST_ADDRESS


async def test_manual_normalizes_mac_with_hyphens(hass: HomeAssistant) -> None:
    """Manual MAC entry with hyphens is normalized to colons."""
    with patch(
        "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ".async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_ADDRESS: TEST_ADDRESS.replace(":", "-"),
                CONF_PIN: DEFAULT_PIN,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == TEST_ADDRESS


async def test_manual_rejects_invalid_mac(hass: HomeAssistant) -> None:
    """Manual MAC entry with invalid format shows an error."""
    with patch(
        "homeassistant.components.diesel_heater.config_flow.bluetooth"
        ".async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: "not-a-mac", CONF_PIN: DEFAULT_PIN},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ADDRESS: "invalid_mac"}


async def test_options_flow_updates_pin_and_presets(hass: HomeAssistant) -> None:
    """Options flow updates the PIN and preset temperatures."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_PIN: DEFAULT_PIN},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_PIN: 9999,
            CONF_PRESET_AWAY_TEMP: 10,
            CONF_PRESET_COMFORT_TEMP: 25,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PIN] == 9999
    assert result["data"][CONF_PRESET_AWAY_TEMP] == 10
    assert result["data"][CONF_PRESET_COMFORT_TEMP] == 25


async def test_options_flow_defaults_match_constants(hass: HomeAssistant) -> None:
    """Options flow uses the configured defaults when the entry has no options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_PIN: DEFAULT_PIN},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema_defaults = {
        k.schema: k.default()
        for k in result["data_schema"].schema
        if hasattr(k, "schema") and callable(k.default)
    }

    assert schema_defaults[CONF_PIN] == DEFAULT_PIN
    assert schema_defaults[CONF_PRESET_AWAY_TEMP] == DEFAULT_PRESET_AWAY_TEMP
    assert schema_defaults[CONF_PRESET_COMFORT_TEMP] == DEFAULT_PRESET_COMFORT_TEMP
