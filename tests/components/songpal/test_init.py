"""Tests songpal setup."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import songpal
from homeassistant.components.songpal.const import CONF_ENDPOINT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir, translation
from homeassistant.setup import async_setup_component

from . import (
    CONF_DATA,
    _create_mocked_device,
    _patch_config_flow_device,
    _patch_media_player_device,
)


def _patch_media_setup():
    """Patch media_player.async_setup_entry."""

    async def _async_return():
        return True

    return patch(
        "homeassistant.components.songpal.media_player.async_setup_entry",
        side_effect=_async_return,
    )


async def test_setup_empty(hass: HomeAssistant) -> None:
    """Test setup without any configuration."""
    with _patch_media_setup() as setup:
        assert await async_setup_component(hass, songpal.DOMAIN, {}) is True
        await hass.async_block_till_done()
    setup.assert_not_called()


async def test_setup(hass: HomeAssistant, issue_registry: ir.IssueRegistry) -> None:
    """Test setup the platform from YAML creates the deprecation issue."""
    mocked_device = _create_mocked_device()

    with _patch_config_flow_device(mocked_device), _patch_media_setup() as setup:
        assert (
            await async_setup_component(
                hass, songpal.DOMAIN, {songpal.DOMAIN: [CONF_DATA]}
            )
            is True
        )
        await hass.async_block_till_done()
    mocked_device.get_supported_methods.assert_called_once()
    setup.assert_called_once()

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{songpal.DOMAIN}"
    )
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.issue_domain == songpal.DOMAIN
    assert issue.translation_key == "deprecated_yaml"
    assert issue.translation_placeholders == {
        "domain": songpal.DOMAIN,
        "integration_title": "Sony Songpal",
    }
    assert len(issue_registry.issues) == 1


@pytest.mark.parametrize(
    "mocked_device",
    [
        pytest.param(_create_mocked_device(), id="online"),
        pytest.param(_create_mocked_device(throw_exception=True), id="offline"),
    ],
)
async def test_setup_already_configured(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, mocked_device: MagicMock
) -> None:
    """Test YAML import of an existing device creates the deprecation issue."""
    MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA).add_to_hass(hass)

    with _patch_config_flow_device(mocked_device), _patch_media_setup():
        assert await async_setup_component(
            hass, songpal.DOMAIN, {songpal.DOMAIN: [CONF_DATA]}
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(songpal.DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{songpal.DOMAIN}"
    )
    assert len(issue_registry.issues) == 1


@pytest.mark.parametrize(
    ("mocked_device", "reason"),
    [
        pytest.param(
            _create_mocked_device(throw_exception=True),
            "cannot_connect",
            id="cannot_connect",
        ),
    ],
)
async def test_setup_import_failed(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mocked_device: MagicMock,
    reason: str,
) -> None:
    """Test a failed YAML import creates an import issue."""
    with _patch_config_flow_device(mocked_device), _patch_media_setup() as setup:
        assert await async_setup_component(
            hass, songpal.DOMAIN, {songpal.DOMAIN: [CONF_DATA]}
        )
        await hass.async_block_till_done()

    setup.assert_not_called()
    assert not hass.config_entries.async_entries(songpal.DOMAIN)
    issue = issue_registry.async_get_issue(
        songpal.DOMAIN, f"deprecated_yaml_import_issue_{reason}"
    )
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.issue_domain == songpal.DOMAIN
    assert issue.translation_key == f"deprecated_yaml_import_issue_{reason}"
    assert issue.translation_placeholders == {
        "domain": songpal.DOMAIN,
        "integration_title": "Sony Songpal",
    }
    assert len(issue_registry.issues) == 1


async def test_unload(hass: HomeAssistant) -> None:
    """Test unload entity."""
    entry = MockConfigEntry(domain=songpal.DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)
    mocked_device = _create_mocked_device()

    with (
        _patch_config_flow_device(mocked_device),
        _patch_media_player_device(mocked_device),
    ):
        assert await async_setup_component(hass, songpal.DOMAIN, {}) is True
        await hass.async_block_till_done()
    mocked_device.listen_notifications.assert_called_once()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    mocked_device.stop_listen_notifications.assert_called_once()


async def test_setup_import_partial_failure(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a failed device import prevents the remove-your-YAML issue."""
    offline_endpoint = "http://0.0.0.1:10000/sony"
    devices = {
        CONF_DATA[CONF_ENDPOINT]: _create_mocked_device(),
        offline_endpoint: _create_mocked_device(throw_exception=True),
    }
    config = [CONF_DATA, {**CONF_DATA, CONF_ENDPOINT: offline_endpoint}]

    with (
        patch(
            "homeassistant.components.songpal.config_flow.Device",
            side_effect=devices.__getitem__,
        ),
        _patch_media_setup(),
    ):
        assert await async_setup_component(
            hass, songpal.DOMAIN, {songpal.DOMAIN: config}
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(songpal.DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        songpal.DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert len(issue_registry.issues) == 1


async def test_setup_import_finishes_before_setup_returns(hass: HomeAssistant) -> None:
    """Test all YAML devices are imported before the integration setup returns."""
    await translation.async_load_integrations(hass, {songpal.DOMAIN})
    second_endpoint = "http://0.0.0.1:10000/sony"
    devices = {
        CONF_DATA[CONF_ENDPOINT]: _create_mocked_device(),
        second_endpoint: _create_mocked_device(),
    }
    config = [CONF_DATA, {**CONF_DATA, CONF_ENDPOINT: second_endpoint}]

    with (
        patch(
            "homeassistant.components.songpal.config_flow.Device",
            side_effect=devices.__getitem__,
        ),
        _patch_media_setup(),
    ):
        assert await async_setup_component(
            hass, songpal.DOMAIN, {songpal.DOMAIN: config}
        )

        assert len(hass.config_entries.async_entries(songpal.DOMAIN)) == 2
