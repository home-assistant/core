"""Test the SpaceAPI config flow."""

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.spaceapi.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {
    "space": "Home",
    "logo": "https://home-assistant.io/logo.png",
    "url": "https://home-assistant.io",
    "entity_id": "binary_sensor.front_door",
    "email": "hello@home-assistant.io",
}

YAML_CONFIG = {
    "space": "Home",
    "logo": "https://home-assistant.io/logo.png",
    "url": "https://home-assistant.io",
    "location": {"address": "In your Home"},
    "contact": {
        "email": "hello@home-assistant.io",
        "jabber": "space@conference.jabber.org",
        "identica": "space_identica",
        "foursquare": "space_foursquare",
    },
    "issue_report_channels": ["email"],
    "state": {
        "entity_id": "test.test_door",
        "icon_open": "https://home-assistant.io/open.png",
        "icon_closed": "https://home-assistant.io/close.png",
    },
    "sensors": {
        "temperature": ["test.temp1"],
        "humidity": ["test.hum1"],
    },
    "spacefed": {"spacenet": True, "spacesaml": False, "spacephone": True},
}


async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the happy path of the user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"] == {
        "space": "Home",
        "logo": "https://home-assistant.io/logo.png",
        "url": "https://home-assistant.io",
        "state": {"entity_id": "binary_sensor.front_door"},
        "contact": {"email": "hello@home-assistant.io"},
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the user flow aborts when an entry already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Existing",
            "logo": "https://example.com/logo.png",
            "url": "https://example.com",
            "state": {"entity_id": "binary_sensor.door"},
            "contact": {"email": "test@example.com"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_import_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test importing full YAML config splits data and options correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=YAML_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"] == {
        "space": "Home",
        "logo": "https://home-assistant.io/logo.png",
        "url": "https://home-assistant.io",
        "state": {"entity_id": "test.test_door"},
        "contact": {"email": "hello@home-assistant.io"},
    }
    # Verify jabber was renamed to xmpp
    assert "jabber" not in result["options"].get("contact", {})
    assert result["options"]["contact"]["xmpp"] == "space@conference.jabber.org"
    # Verify dropped fields are not present
    assert "identica" not in result["options"].get("contact", {})
    assert "foursquare" not in result["options"].get("contact", {})
    assert "spacephone" not in result["options"].get("spacefed", {})
    assert "stream" not in result["options"]
    assert "cache" not in result["options"]
    assert "radio_show" not in result["options"]
    assert result["options"] == {
        "contact": {"xmpp": "space@conference.jabber.org"},
        "state": {
            "icon_open": "https://home-assistant.io/open.png",
            "icon_closed": "https://home-assistant.io/close.png",
        },
        "sensors": {
            "temperature": ["test.temp1"],
            "humidity": ["test.hum1"],
        },
        "spacefed": {"spacenet": True, "spacesaml": False},
        "location": {"address": "In your Home"},
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test import flow aborts when an entry already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Existing",
            "logo": "https://example.com/logo.png",
            "url": "https://example.com",
            "state": {"entity_id": "binary_sensor.door"},
            "contact": {"email": "test@example.com"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=YAML_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfiguration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "OldSpace",
            "logo": "https://example.com/old.png",
            "url": "https://example.com",
            "state": {"entity_id": "binary_sensor.door"},
            "contact": {"email": "old@example.com"},
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "space": "NewSpace",
            "logo": "https://example.com/new.png",
            "url": "https://example.com/new",
            "entity_id": "binary_sensor.new_door",
            "email": "new@example.com",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["space"] == "NewSpace"
    assert entry.data["state"]["entity_id"] == "binary_sensor.new_door"
    assert entry.data["contact"]["email"] == "new@example.com"


async def test_options_flow_menu(hass: HomeAssistant) -> None:
    """Test options flow shows the menu with all sub-menu options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
            "contact": {"email": "hello@home-assistant.io"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    assert result["menu_options"] == [
        "contact",
        "state_icons",
        "sensors",
        "spacefed",
        "media",
        "feeds",
        "other",
    ]


async def test_options_flow_contact(hass: HomeAssistant) -> None:
    """Test options flow contact sub-menu saves contact details."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
            "contact": {"email": "hello@home-assistant.io"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "contact"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "contact"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "email": "",
            "irc": "#hackerspace",
            "ml": "list@hackerspace.org",
            "phone": "",
            "sip": "",
            "twitter": "@hackerspace",
            "facebook": "",
            "mastodon": "",
            "matrix": "",
            "xmpp": "",
            "mumble": "",
            "gopher": "",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["contact"] == {
        "irc": "#hackerspace",
        "ml": "list@hackerspace.org",
        "twitter": "@hackerspace",
    }


async def test_options_flow_contact_empty_clears(hass: HomeAssistant) -> None:
    """Test options flow contact clears section when all fields are empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
            "contact": {"email": "hello@home-assistant.io"},
        },
        options={"contact": {"irc": "#old"}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "contact"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "email": "",
            "irc": "",
            "ml": "",
            "phone": "",
            "sip": "",
            "twitter": "",
            "facebook": "",
            "mastodon": "",
            "matrix": "",
            "xmpp": "",
            "mumble": "",
            "gopher": "",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "contact" not in result["data"]


async def test_options_flow_sensors(hass: HomeAssistant) -> None:
    """Test options flow sensors sub-menu saves entity selections."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
            "contact": {"email": "hello@home-assistant.io"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "sensors"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "temperature": ["sensor.temp1", "sensor.temp2"],
            "humidity": ["sensor.hum1"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["sensors"] == {
        "temperature": ["sensor.temp1", "sensor.temp2"],
        "humidity": ["sensor.hum1"],
    }


async def test_options_flow_spacefed(hass: HomeAssistant) -> None:
    """Test options flow spacefed sub-menu saves boolean values."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
            "contact": {"email": "hello@home-assistant.io"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "spacefed"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "spacefed"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "spacenet": True,
            "spacesaml": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["spacefed"] == {
        "spacenet": True,
        "spacesaml": False,
    }
