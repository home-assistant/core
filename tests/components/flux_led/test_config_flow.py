"""Define tests for the Flux LED/Magic Home config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.flux_led.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TYPE

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_manual_form(hass):
    """Test the manual configuration form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TYPE: "manual",
        },
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "manual"

    with patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb._send_msg",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb._read_msg",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb._determine_query_len",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb.query_state",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb.update_state",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb.mode",
        return_value="valid",
    ), patch(
        "homeassistant.components.flux_led.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.flux_led.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_NAME: "TestLight",
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "TestLight"
    assert result3["data"] == {
        CONF_NAME: "TestLight",
        CONF_HOST: "1.1.1.1",
        CONF_TYPE: "manual",
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_form_broken_pipe(hass):
    """Test the manual configuration form with cannot_connect to light."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TYPE: "manual",
        },
    )

    assert result2["type"] == "form"
    assert result2["step_id"] == "manual"

    with patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb.connect",
        side_effect=BrokenPipeError(),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_NAME: "TestLight",
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result3["type"] == "form"
    assert result3["step_id"] == "manual"
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_auto_form(hass):
    """Test the auto configured setup form."""

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
        "homeassistant.components.flux_led.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.flux_led.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TYPE: "auto",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Auto Search"
    assert result2["data"] == {CONF_TYPE: "auto"}

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_auto_form_no_devices_found(hass):
    """Test the auto configuration with no devices found."""

    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flux_led.BulbScanner.scan",
        return_value=[],
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TYPE: "auto",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "abort"
    assert result3["reason"] == "no_devices_found"


async def test_import_auto(hass):
    """Test the config_flow when the source is an import from YAML."""

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
        "homeassistant.components.flux_led.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.flux_led.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_TYPE: "auto"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Auto Search"
    assert result["data"] == {CONF_TYPE: "auto"}

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_auto_import_already_setup(hass):
    """Test where the auto configuration from YAML has already been set up."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="flux_led_auto",
        data={
            CONF_TYPE: "auto",
        },
    ).add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_IMPORT,
        },
        data={CONF_TYPE: "auto"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured_device"


async def test_manual_import(hass):
    """Test the config flow for manual import from YAML."""

    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb._send_msg",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb._read_msg",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb._determine_query_len",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb.query_state",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb.update_state",
        return_value=True,
    ), patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb.mode",
        return_value="valid",
    ), patch(
        "homeassistant.components.flux_led.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.flux_led.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_TYPE: "manual",
                CONF_NAME: "TestLight",
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "TestLight"
    assert result["data"] == {
        CONF_NAME: "TestLight",
        CONF_HOST: "1.1.1.1",
        CONF_TYPE: "manual",
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_import_broken_pipe(hass):
    """Test the config flow for manual import with cannot_connect from YAML."""

    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.flux_led.config_flow.WifiLedBulb.connect",
        side_effect=BrokenPipeError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_TYPE: "manual",
                CONF_NAME: "TestLight",
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_manual_import_already_setup(hass):
    """Test the manual import flow where the light is already set up."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="flux_led_1_1_1_1",
        data={
            CONF_TYPE: "manual",
            CONF_NAME: "TestLight",
            CONF_HOST: "1.1.1.1",
        },
    ).add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_TYPE: "manual",
            CONF_NAME: "TestLight",
            CONF_HOST: "1.1.1.1",
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured_device"
