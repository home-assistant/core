"""Define tests for the Flux LED/Magic Home config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.flux_led.const import (
    CONF_AUTOMATIC_ADD,
    CONF_EFFECT_SPEED,
    DEFAULT_EFFECT_SPEED,
    DOMAIN,
)
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_NAME

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_setup_form(hass):
    """Test we get the setup confirm form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_setup_automatic_add(hass):
    """Test the results with automatic add set to True."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flux_led.light.BulbScanner.scan",
        return_value=[
            {
                "ipaddr": "1.1.1.1",
                "id": "test_id",
                "model": "test_model",
            }
        ],
    ), patch(
        "homeassistant.components.flux_led.light.BulbScanner.getBulbInfo",
        return_value=[
            {
                "ipaddr": "1.1.1.1",
                "id": "test_id",
                "model": "test_model",
            }
        ],
    ), patch(
        "homeassistant.components.flux_led.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.flux_led.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_AUTOMATIC_ADD: True,
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "FluxLED/MagicHome"
    assert result2["data"] == {
        CONF_AUTOMATIC_ADD: True,
        CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
        CONF_DEVICES: {"1_1_1_1": {CONF_NAME: "1.1.1.1", CONF_HOST: "1.1.1.1"}},
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_setup_manual_add(hass):
    """Test the results with automatic add set to False."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flux_led.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.flux_led.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_AUTOMATIC_ADD: False,
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "FluxLED/MagicHome"
    assert result2["data"] == {
        CONF_AUTOMATIC_ADD: False,
        CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
        CONF_DEVICES: {},
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(hass):
    """Test config flow when flux_led component is already setup."""
    MockConfigEntry(
        domain="flux_led",
        data={
            CONF_AUTOMATIC_ADD: False,
            CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
            CONF_DEVICES: {},
        },
    ).add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_import_automatic_add(hass):
    """Test the import of an existing configuration when automatic add is enabled."""

    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.flux_led.light.BulbScanner.scan",
        return_value=[
            {
                "ipaddr": "1.1.1.1",
                "id": "test_id",
                "model": "test_model",
            }
        ],
    ), patch(
        "homeassistant.components.flux_led.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.flux_led.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_AUTOMATIC_ADD: True},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "FluxLED/MagicHome"
    assert result2["data"] == {
        CONF_AUTOMATIC_ADD: True,
        CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
        CONF_DEVICES: {},
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_automatic_add_already_setup(hass):
    """Test import auto added when the integration is already configured."""
    MockConfigEntry(
        domain="flux_led",
        data={
            CONF_AUTOMATIC_ADD: False,
            CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
            CONF_DEVICES: {},
        },
    ).add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.flux_led.light.BulbScanner.scan",
        return_value=[
            {
                "ipaddr": "1.1.1.1",
                "id": "test_id",
                "model": "test_model",
            }
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_AUTOMATIC_ADD: True},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_import_manual(hass):
    """Test the import of an existing manual configuration."""

    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.flux_led.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.flux_led.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_AUTOMATIC_ADD: False,
                CONF_DEVICES: {
                    "1_1_1_1": {
                        CONF_NAME: "TestLight",
                        CONF_HOST: "1.1.1.1",
                    }
                },
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "FluxLED/MagicHome"
    assert result2["data"] == {
        CONF_AUTOMATIC_ADD: False,
        CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
        CONF_DEVICES: {
            "1_1_1_1": {
                CONF_NAME: "TestLight",
                CONF_HOST: "1.1.1.1",
            }
        },
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_manual_already_setup(hass):
    """Test import manual added when the device is already configured."""
    MockConfigEntry(
        domain="flux_led",
        data={
            CONF_AUTOMATIC_ADD: False,
            CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
            CONF_DEVICES: {
                "1_1_1_1": {
                    CONF_NAME: "TestLight",
                    CONF_HOST: "1.1.1.1",
                }
            },
        },
    ).add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_AUTOMATIC_ADD: False,
            CONF_DEVICES: {
                "1_1_1_1": {
                    CONF_NAME: "TestLight",
                    CONF_HOST: "1.1.1.1",
                }
            },
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"
