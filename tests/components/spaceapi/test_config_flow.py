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
        "issue_mail": "issues@home-assistant.io",
        "google": "should-be-dropped",
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
    }
    assert result["options"]["contact"]["email"] == "hello@home-assistant.io"
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
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    assert len(mock_setup_entry.mock_calls) == 0


# ---------------------------------------------------------------------------
# YAML import tests — remove entire block when YAML import is dropped (2026.12)
# ---------------------------------------------------------------------------


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
    }
    # Verify jabber was renamed to xmpp and email is in options
    assert "jabber" not in result["options"].get("contact", {})
    assert result["options"]["contact"]["email"] == "hello@home-assistant.io"
    assert result["options"]["contact"]["xmpp"] == "space@conference.jabber.org"
    # Fields still valid in v15 are kept; "google" (removed in v15) is dropped
    assert result["options"]["contact"]["identica"] == "space_identica"
    assert result["options"]["contact"]["foursquare"] == "space_foursquare"
    assert result["options"]["contact"]["issue_mail"] == "issues@home-assistant.io"
    assert "google" not in result["options"].get("contact", {})
    assert "spacephone" not in result["options"].get("spacefed", {})
    assert "stream" not in result["options"]
    assert "cache" not in result["options"]
    assert "radio_show" not in result["options"]
    assert result["options"] == {
        "contact": {
            "email": "hello@home-assistant.io",
            "xmpp": "space@conference.jabber.org",
            "identica": "space_identica",
            "foursquare": "space_foursquare",
            "issue_mail": "issues@home-assistant.io",
        },
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


async def test_import_flow_already_configured(  # remove with YAML import (2026.12)
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
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=YAML_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_import_flow_feeds_flicker_renamed(  # remove with YAML import (2026.12)
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test import flow renames legacy 'flicker' feed key to 'flickr'."""
    yaml_config = {
        **YAML_CONFIG,
        "feeds": {
            "flicker": {"url": "https://flickr.com/photos/space", "type": "rss"},
        },
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=yaml_config,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "flicker" not in result["options"].get("feeds", {})
    assert result["options"]["feeds"]["flickr"] == {
        "url": "https://flickr.com/photos/space",
        "type": "rss",
    }


async def test_import_flow_no_location(  # remove with YAML import (2026.12)
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test import flow when YAML has no location section."""
    yaml_config = {k: v for k, v in YAML_CONFIG.items() if k != "location"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=yaml_config,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "location" not in result["options"]


async def test_import_flow_cam_and_projects(  # remove with YAML import (2026.12)
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test import flow passes through cam and projects lists."""
    yaml_config = {
        **YAML_CONFIG,
        "cam": ["https://example.com/cam1", "https://example.com/cam2"],
        "projects": ["https://example.com/proj1"],
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=yaml_config,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["cam"] == [
        "https://example.com/cam1",
        "https://example.com/cam2",
    ]
    assert result["options"]["projects"] == ["https://example.com/proj1"]


async def test_import_flow_contact_no_email(  # remove with YAML import (2026.12)
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test import flow when contact has only jabber (renamed xmpp) and no email."""
    yaml_config = {
        **YAML_CONFIG,
        "contact": {"jabber": "space@xmpp.example.com"},
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=yaml_config,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    contact = result["options"].get("contact", {})
    assert "email" not in contact
    assert contact["xmpp"] == "space@xmpp.example.com"


# ---------------------------------------------------------------------------
# End of YAML import tests
# ---------------------------------------------------------------------------


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfiguration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "OldSpace",
            "logo": "https://example.com/old.png",
            "url": "https://example.com",
            "state": {"entity_id": "binary_sensor.door"},
        },
        options={"contact": {"email": "old@example.com"}},
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
    assert "contact" not in entry.data
    assert entry.options["contact"]["email"] == "new@example.com"


async def test_options_flow_menu(hass: HomeAssistant) -> None:
    """Test options flow shows the menu with all sub-menu options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    assert result["menu_options"] == [
        "contact",
        "state_extras",
        "sensors",
        "spacefed",
        "location",
        "media",
        "feeds",
        "projects",
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
            "issue_mail": "issues@hackerspace.org",
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
            "identica": "",
            "foursquare": "",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["contact"] == {
        "issue_mail": "issues@hackerspace.org",
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
            "issue_mail": "",
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
            "identica": "",
            "foursquare": "",
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


async def test_options_flow_state_extras(hass: HomeAssistant) -> None:
    """Test options flow state_extras sub-menu saves icons and state text."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "state_extras"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "state_extras"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "icon_open": "https://example.com/open.png",
            "icon_closed": "https://example.com/closed.png",
            "message": "input_text.state_message",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["state"] == {
        "icon_open": "https://example.com/open.png",
        "icon_closed": "https://example.com/closed.png",
        "message": "input_text.state_message",
    }


async def test_options_flow_location(hass: HomeAssistant) -> None:
    """Test options flow location sub-menu saves location details."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "location"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "location"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "address": "1 Main St",
            "timezone": "Europe/Vienna",
            "country_code": "AT",
            "hint": "Ring the bell",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["location"] == {
        "address": "1 Main St",
        "timezone": "Europe/Vienna",
        "country_code": "AT",
        "hint": "Ring the bell",
    }


async def test_options_flow_media(hass: HomeAssistant) -> None:
    """Test options flow media sub-menu saves camera URLs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "media"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "media"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"cam": ["https://example.com/cam1", "https://example.com/cam2"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["cam"] == [
        "https://example.com/cam1",
        "https://example.com/cam2",
    ]


async def test_options_flow_feeds(hass: HomeAssistant) -> None:
    """Test options flow feeds sub-menu saves feed URLs and types."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "feeds"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "feeds"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "blog_url": "https://example.com/blog",
            "blog_type": "atom",
            "wiki_url": "",
            "wiki_type": "",
            "calendar_url": "",
            "calendar_type": "",
            "flickr_url": "https://flickr.com/photos/space",
            "flickr_type": "",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["feeds"] == {
        "blog": {"url": "https://example.com/blog", "type": "atom"},
        "flickr": {"url": "https://flickr.com/photos/space"},
    }


async def test_options_flow_feeds_flicker_migration(hass: HomeAssistant) -> None:
    """Test that legacy 'flicker' feed key is migrated to 'flickr' on options edit."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
        },
        options={
            "feeds": {
                "flicker": {"url": "https://flickr.com/photos/old"},
            }
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "feeds"},
    )
    assert result["type"] is FlowResultType.FORM

    # Submit without changes — legacy "flicker" should become "flickr"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "blog_url": "",
            "blog_type": "",
            "wiki_url": "",
            "wiki_type": "",
            "calendar_url": "",
            "calendar_type": "",
            "flickr_url": "https://flickr.com/photos/old",
            "flickr_type": "",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "flicker" not in result["data"].get("feeds", {})
    assert result["data"]["feeds"]["flickr"] == {"url": "https://flickr.com/photos/old"}


async def test_options_flow_projects(hass: HomeAssistant) -> None:
    """Test options flow projects sub-menu saves project URLs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "space": "Home",
            "logo": "https://home-assistant.io/logo.png",
            "url": "https://home-assistant.io",
            "state": {"entity_id": "binary_sensor.front_door"},
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "projects"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "projects"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"projects": ["https://example.com/proj1", "https://example.com/proj2"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["projects"] == [
        "https://example.com/proj1",
        "https://example.com/proj2",
    ]


# ---------------------------------------------------------------------------
# Options-flow clearing tests
# ---------------------------------------------------------------------------

_BASE_DATA = {
    "space": "Home",
    "logo": "https://home-assistant.io/logo.png",
    "url": "https://home-assistant.io",
    "state": {"entity_id": "binary_sensor.front_door"},
}


async def test_options_flow_state_extras_empty_clears(hass: HomeAssistant) -> None:
    """Test state_extras clears the state option when all fields are empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_BASE_DATA,
        options={"state": {"icon_open": "https://example.com/open.png"}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "state_extras"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"icon_open": "", "icon_closed": ""}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "state" not in result["data"]


async def test_options_flow_sensors_empty_clears(hass: HomeAssistant) -> None:
    """Test sensors clears the sensors option when no entities are selected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_BASE_DATA,
        options={"sensors": {"temperature": ["sensor.t1"]}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "sensors"}
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "sensors" not in result["data"]


async def test_options_flow_spacefed_all_false_clears(hass: HomeAssistant) -> None:
    """Test spacefed clears the spacefed option when both booleans are false."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_BASE_DATA,
        options={"spacefed": {"spacenet": True, "spacesaml": True}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "spacefed"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"spacenet": False, "spacesaml": False}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "spacefed" not in result["data"]


async def test_options_flow_location_empty_clears(hass: HomeAssistant) -> None:
    """Test location clears the location option when all fields are empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_BASE_DATA,
        options={"location": {"address": "Old St"}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "location"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"address": "", "timezone": "", "country_code": "", "hint": ""},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "location" not in result["data"]


async def test_options_flow_media_empty_clears(hass: HomeAssistant) -> None:
    """Test media clears the cam option when the list is empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_BASE_DATA,
        options={"cam": ["https://example.com/cam1"]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "media"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"cam": []}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "cam" not in result["data"]


async def test_options_flow_feeds_empty_clears(hass: HomeAssistant) -> None:
    """Test feeds clears the feeds option when all URL fields are empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_BASE_DATA,
        options={"feeds": {"blog": {"url": "https://example.com/blog"}}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "feeds"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "blog_url": "",
            "blog_type": "",
            "wiki_url": "",
            "wiki_type": "",
            "calendar_url": "",
            "calendar_type": "",
            "flickr_url": "",
            "flickr_type": "",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "feeds" not in result["data"]


async def test_options_flow_projects_empty_clears(hass: HomeAssistant) -> None:
    """Test projects step clears the projects option when the list is empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_BASE_DATA,
        options={"projects": ["https://example.com/proj"]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "projects"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"projects": []}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "projects" not in result["data"]


# ---------------------------------------------------------------------------
# Subentry reconfigure tests
# ---------------------------------------------------------------------------
