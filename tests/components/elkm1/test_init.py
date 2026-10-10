"""Tests for the Elk-M1 Control init."""

from unittest.mock import MagicMock, patch

from homeassistant.components.elkm1.const import CONF_AUTO_CONFIGURE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PREFIX, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_MAC, _patch_discovery, mock_elk

from tests.common import MockConfigEntry


def _mocked_elk_with_light() -> MagicMock:
    """Return a mocked Elk that exposes a single PLC light and nothing else."""
    light = MagicMock()
    light.index = 0
    light.name = "Test Light"
    light.default_name.return_value = "test_light"
    light.configured = True
    light.status = 0
    light.as_dict.return_value = {}

    elk = mock_elk(sync_complete=True)
    elk.is_connected.return_value = True
    for collection in (
        "areas",
        "tasks",
        "counters",
        "keypads",
        "zones",
        "outputs",
        "settings",
        "thermostats",
    ):
        setattr(elk, collection, [])
    elk.lights = [light]
    # The panel sensor is an attached entity; skip it so the only registered
    # device besides the system device is the light's own (via_device) device.
    elk.panel.configured = False
    elk.panel.elkm1_version = "1.0.0"
    elk.panel.temperature_units = "F"
    return elk


async def test_light_via_device_links_to_system_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A child (light) device links to the system device registered at setup.

    With auto configure and only a light present, no sibling attached entity
    creates the system device, so the link resolves only because setup
    registers the system device before platforms are forwarded.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "elks://1.2.3.4",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_PREFIX: "",
            "auto_configure": True,
        },
        unique_id=MOCK_MAC,
    )
    config_entry.add_to_hass(hass)

    with (
        _patch_discovery(),
        patch(
            "homeassistant.components.elkm1.Elk",
            return_value=_mocked_elk_with_light(),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    system_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "_system"), config_entry.entry_id
    )
    assert system_device is not None
    assert system_device.name == "ElkM1"

    light_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "elkm1_test_light"), config_entry.entry_id
    )
    assert light_device is not None
    assert light_device.via_device_id == system_device.id


async def test_login_failed(hass: HomeAssistant) -> None:
    """Test setup fails when login to the panel fails."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "elks://1.2.3.4",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_PREFIX: "",
            CONF_AUTO_CONFIGURE: True,
        },
        unique_id=MOCK_MAC,
    )
    config_entry.add_to_hass(hass)

    with (
        _patch_discovery(),
        patch(
            "homeassistant.components.elkm1.Elk",
            return_value=mock_elk(invalid_auth=True),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.reason == "ElkM1 login failed for elks://1.2.3.4"


async def test_invalid_config_item(hass: HomeAssistant) -> None:
    """Test setup fails when a configured range is invalid."""
    disabled = {"enabled": False, "exclude": [], "include": []}
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "elks://1.2.3.4",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_PREFIX: "",
            CONF_AUTO_CONFIGURE: False,
            "area": {"enabled": True, "exclude": [], "include": [[1, 99]]},
            "counter": disabled,
            "keypad": disabled,
            "output": disabled,
            "plc": disabled,
            "setting": disabled,
            "task": disabled,
            "thermostat": disabled,
            "zone": disabled,
        },
        unique_id=MOCK_MAC,
    )
    config_entry.add_to_hass(hass)

    with _patch_discovery():
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.reason == "Invalid configuration for area"
