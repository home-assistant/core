"""Define tests for the Flux LED/Magic Home config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.flux_led.const import (
    CONF_AUTOMATIC_ADD,
    CONF_CONFIGURE_DEVICE,
    CONF_EFFECT_SPEED,
    CONF_REMOVE_DEVICE,
    DEFAULT_EFFECT_SPEED,
    DOMAIN,
)
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_NAME

from tests.common import MockConfigEntry


async def test_setup_form(hass):
    """Test we get the setup confirm form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]


async def test_setup_automatic_add(hass):
    """Test the results with automatic add set to True."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flux_led.BulbScanner.scan",
        return_value=[
            {
                "ipaddr": "1.1.1.1",
                "id": "test_id",
                "model": "test_model",
            }
        ],
    ), patch(
        "homeassistant.components.flux_led.BulbScanner.getBulbInfo",
        return_value=[
            {
                "ipaddr": "1.1.1.1",
                "id": "test_id",
                "model": "test_model",
            }
        ],
    ), patch(
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

    assert len(mock_setup_entry.mock_calls) == 1


async def test_setup_manual_add(hass):
    """Test the results with automatic add set to False."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
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
        "homeassistant.components.flux_led.BulbScanner.scan",
        return_value=[
            {
                "ipaddr": "1.1.1.1",
                "id": "test_id",
                "model": "test_model",
            }
        ],
    ), patch(
        "homeassistant.components.flux_led.BulbScanner.getBulbInfo",
        return_value=[
            {
                "ipaddr": "1.1.1.1",
                "id": "test_id",
                "model": "test_model",
            }
        ],
    ), patch(
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
        CONF_DEVICES: {"1_1_1_1": {CONF_NAME: "1.1.1.1", CONF_HOST: "1.1.1.1"}},
    }

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
        "homeassistant.components.flux_led.BulbScanner.scan",
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


async def test_options_set_global_options(hass):
    """Test set global options through options flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
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
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flux_led.BulbScanner.scan",
        return_value=[
            {
                "ipaddr": "1.1.1.1",
                "id": "test_id",
                "model": "test_model",
            }
        ],
    ), patch(
        "homeassistant.components.flux_led.light.WifiLedBulb.connect",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AUTOMATIC_ADD: True, CONF_EFFECT_SPEED: 80},
    )

    assert result2["type"] == "create_entry"
    assert result2["data"] == {
        "global": {
            CONF_AUTOMATIC_ADD: True,
            CONF_EFFECT_SPEED: 80,
        }
    }


async def test_options_add_and_remove_new_light(hass):
    """Test manual adding and removing of new light through options flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
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
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flux_led.BulbScanner.scan",
        return_value=[
            {
                "ipaddr": "1.1.1.1",
                "id": "test_id",
                "model": "test_model",
            }
        ],
    ), patch(
        "homeassistant.components.flux_led.light.WifiLedBulb.connect",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.1.1.2", CONF_NAME: "TestLight2"},
    )

    assert result2["type"] == "create_entry"
    assert result2["data"] == {
        "global": {
            CONF_AUTOMATIC_ADD: False,
            CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
        },
    }

    assert entry.data == {
        CONF_AUTOMATIC_ADD: False,
        CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
        CONF_DEVICES: {
            "1_1_1_1": {
                CONF_NAME: "TestLight",
                CONF_HOST: "1.1.1.1",
            },
            "1_1_1_2": {
                CONF_NAME: "TestLight2",
                CONF_HOST: "1.1.1.2",
            },
        },
    }

    # Remove the new light.
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOVE_DEVICE: "1_1_1_2"},
    )

    assert result2["type"] == "create_entry"
    assert result2["data"] == {
        "global": {
            CONF_AUTOMATIC_ADD: False,
            CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
        }
    }

    assert entry.data == {
        CONF_AUTOMATIC_ADD: False,
        CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
        CONF_DEVICES: {
            "1_1_1_1": {
                CONF_NAME: "TestLight",
                CONF_HOST: "1.1.1.1",
            },
        },
    }


async def test_options_configure_light(hass):
    """Test configuration of a light through options flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
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
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flux_led.BulbScanner.scan",
        return_value=[
            {
                "ipaddr": "1.1.1.1",
                "id": "test_id",
                "model": "test_model",
            }
        ],
    ), patch(
        "homeassistant.components.flux_led.light.WifiLedBulb.connect",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_CONFIGURE_DEVICE: "1_1_1_1"},
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "configure_device"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={CONF_EFFECT_SPEED: 80},
    )

    assert result3["type"] == "create_entry"
    assert result3["data"] == {
        "global": {
            CONF_AUTOMATIC_ADD: False,
            CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
        },
        "1_1_1_1": {
            CONF_EFFECT_SPEED: 80,
        },
    }
