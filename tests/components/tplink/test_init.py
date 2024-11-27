"""Tests for the TP-Link component."""

from __future__ import annotations

import copy
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory
from kasa import AuthenticationError, DeviceConfig, Feature, KasaException, Module
import pytest

from homeassistant import setup
from homeassistant.components import tplink
from homeassistant.components.tplink.const import (
    CONF_AES_KEYS,
    CONF_CONNECTION_PARAMETERS,
    CONF_CREDENTIALS_HASH,
    CONF_DEVICE_CONFIG,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_ALIAS,
    CONF_AUTHENTICATION,
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_ON,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    ALIAS,
    CREATE_ENTRY_DATA_AES,
    CREATE_ENTRY_DATA_KLAP,
    CREATE_ENTRY_DATA_LEGACY,
    CREDENTIALS_HASH_AES,
    CREDENTIALS_HASH_KLAP,
    DEVICE_CONFIG_AES,
    DEVICE_CONFIG_DICT_KLAP,
    DEVICE_CONFIG_KLAP,
    DEVICE_CONFIG_LEGACY,
    DEVICE_ID,
    DEVICE_ID_MAC,
    IP_ADDRESS,
    MAC_ADDRESS,
    MODEL,
    _mocked_device,
    _patch_connect,
    _patch_discovery,
    _patch_single_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_configuring_tplink_causes_discovery(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that specifying empty config does discovery."""
    with (
        patch("homeassistant.components.tplink.Discover.discover") as discover,
        patch("homeassistant.components.tplink.Discover.discover_single"),
    ):
        discover.return_value = {MagicMock(): MagicMock()}
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done(wait_background_tasks=True)
        # call_count will differ based on number of broadcast addresses
        call_count = len(discover.mock_calls)
        assert discover.mock_calls

        freezer.tick(tplink.DISCOVERY_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(discover.mock_calls) == call_count * 2

        freezer.tick(tplink.DISCOVERY_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert len(discover.mock_calls) == call_count * 3


async def test_config_entry_reload(hass: HomeAssistant) -> None:
    """Test that a config entry can be reloaded."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state is ConfigEntryState.LOADED
        await hass.config_entries.async_unload(already_migrated_config_entry.entry_id)
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_retry(hass: HomeAssistant) -> None:
    """Test that a config entry can be retried."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    with (
        _patch_discovery(no_device=True),
        _patch_single_discovery(no_device=True),
        _patch_connect(no_device=True),
    ):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_dimmer_switch_unique_id_fix_original_entity_still_exists(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test no migration happens if the original entity id still exists."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=MAC_ADDRESS)
    config_entry.add_to_hass(hass)
    dimmer = _mocked_device(alias="My dimmer", modules=[Module.Light])
    rollout_unique_id = MAC_ADDRESS.replace(":", "").upper()
    original_unique_id = tplink.legacy_device_id(dimmer)
    original_dimmer_entity_reg = entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="light",
        unique_id=original_unique_id,
        original_name="Original dimmer",
    )
    rollout_dimmer_entity_reg = entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="light",
        unique_id=rollout_unique_id,
        original_name="Rollout dimmer",
    )

    with (
        _patch_discovery(device=dimmer),
        _patch_single_discovery(device=dimmer),
        _patch_connect(device=dimmer),
    ):
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done(wait_background_tasks=True)

    migrated_dimmer_entity_reg = entity_registry.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="light",
        unique_id=original_unique_id,
        original_name="Migrated dimmer",
    )
    assert migrated_dimmer_entity_reg.entity_id == original_dimmer_entity_reg.entity_id
    assert migrated_dimmer_entity_reg.entity_id != rollout_dimmer_entity_reg.entity_id


async def test_config_entry_wrong_mac_Address(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test config entry enters setup retry when mac address mismatches."""
    mismatched_mac = f"{MAC_ADDRESS[:-1]}0"
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=mismatched_mac
    )
    already_migrated_config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_single_discovery(), _patch_connect():
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()
        assert already_migrated_config_entry.state is ConfigEntryState.SETUP_RETRY

    assert (
        "Unexpected device found at 127.0.0.1; expected aa:bb:cc:dd:ee:f0, found aa:bb:cc:dd:ee:ff"
        in caplog.text
    )


async def test_config_entry_device_config(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
) -> None:
    """Test that a config entry can be loaded with DeviceConfig."""
    mock_config_entry = MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data={**CREATE_ENTRY_DATA_KLAP},
        unique_id=MAC_ADDRESS,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_entry_with_stored_credentials(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
) -> None:
    """Test that a config entry can be loaded when stored credentials are set."""
    stored_credentials = tplink.Credentials("fake_username1", "fake_password1")
    mock_config_entry = MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data={**CREATE_ENTRY_DATA_KLAP},
        unique_id=MAC_ADDRESS,
    )
    auth = {
        CONF_USERNAME: stored_credentials.username,
        CONF_PASSWORD: stored_credentials.password,
    }

    hass.data.setdefault(DOMAIN, {})[CONF_AUTHENTICATION] = auth
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.tplink.async_create_clientsession", return_value="Foo"
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    config = DeviceConfig.from_dict(DEVICE_CONFIG_KLAP.to_dict())
    config.uses_http = False
    config.http_client = "Foo"
    assert config.credentials != stored_credentials
    config.credentials = stored_credentials
    mock_connect["connect"].assert_called_once_with(config=config)


async def test_config_entry_conn_params_invalid(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that an invalid device config logs an error and loads the config entry."""
    entry_data = copy.deepcopy(CREATE_ENTRY_DATA_KLAP)
    entry_data[CONF_CONNECTION_PARAMETERS] = {"foo": "bar"}
    mock_config_entry = MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data={**entry_data},
        unique_id=MAC_ADDRESS,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert (
        f"Invalid connection parameters dict for {IP_ADDRESS}: {entry_data.get(CONF_CONNECTION_PARAMETERS)}"
        in caplog.text
    )


@pytest.mark.parametrize(
    ("error_type", "entry_state", "reauth_flows"),
    [
        (tplink.AuthenticationError, ConfigEntryState.SETUP_ERROR, True),
        (tplink.KasaException, ConfigEntryState.SETUP_RETRY, False),
    ],
    ids=["invalid-auth", "unknown-error"],
)
async def test_config_entry_errors(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_connect: AsyncMock,
    error_type,
    entry_state,
    reauth_flows,
) -> None:
    """Test that device exceptions are handled correctly during init."""
    mock_connect["connect"].side_effect = error_type
    mock_config_entry = MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data={**CREATE_ENTRY_DATA_KLAP},
        unique_id=MAC_ADDRESS,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is entry_state
    assert (
        any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        == reauth_flows
    )


async def test_plug_auth_fails(hass: HomeAssistant) -> None:
    """Test a smart plug auth failure."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)
    device = _mocked_device(alias="my_plug", features=["state"])
    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_plug"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    device.update = AsyncMock(side_effect=AuthenticationError)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE

    assert (
        len(
            hass.config_entries.flow.async_progress_by_handler(
                DOMAIN, match_context={"source": SOURCE_REAUTH}
            )
        )
        == 1
    )


async def test_update_attrs_fails_in_init(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a smart plug auth failure."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)
    light = _mocked_device(modules=[Module.Light], alias="my_light")
    light_module = light.modules[Module.Light]
    p = PropertyMock(side_effect=KasaException)
    type(light_module).color_temp = p
    light.__str__ = lambda _: "MockLight"
    with _patch_discovery(device=light), _patch_connect(device=light):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"
    entity = entity_registry.async_get(entity_id)
    assert entity
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE
    assert "Unable to read data for MockLight None:" in caplog.text


async def test_update_attrs_fails_on_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a smart plug auth failure."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)
    light = _mocked_device(modules=[Module.Light], alias="my_light")
    light_module = light.modules[Module.Light]

    with _patch_discovery(device=light), _patch_connect(device=light):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_light"
    entity = entity_registry.async_get(entity_id)
    assert entity
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    p = PropertyMock(side_effect=KasaException)
    type(light_module).color_temp = p
    light.__str__ = lambda _: "MockLight"
    freezer.tick(5)
    async_fire_time_changed(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE
    assert f"Unable to read data for MockLight {entity_id}:" in caplog.text
    # Check only logs once
    caplog.clear()
    freezer.tick(5)
    async_fire_time_changed(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE
    assert f"Unable to read data for MockLight {entity_id}:" not in caplog.text


async def test_feature_no_category(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a strip unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    dev = _mocked_device(
        alias="my_plug",
        features=["led"],
    )
    dev.features["led"].category = Feature.Category.Unset
    with _patch_discovery(device=dev), _patch_connect(device=dev):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_plug_led"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert "Unhandled category Category.Unset, fallback to DIAGNOSTIC" in caplog.text


@pytest.mark.parametrize(
    ("device_id", "id_count", "domains", "expected_message"),
    [
        pytest.param(DEVICE_ID_MAC, 1, [DOMAIN], None, id="mac-id-no-children"),
        pytest.param(DEVICE_ID_MAC, 3, [DOMAIN], "Replaced", id="mac-id-children"),
        pytest.param(
            DEVICE_ID_MAC,
            1,
            [DOMAIN, "other"],
            None,
            id="mac-id-no-children-other-domain",
        ),
        pytest.param(
            DEVICE_ID_MAC,
            3,
            [DOMAIN, "other"],
            "Replaced",
            id="mac-id-children-other-domain",
        ),
        pytest.param(DEVICE_ID, 1, [DOMAIN], None, id="not-mac-id-no-children"),
        pytest.param(
            DEVICE_ID, 3, [DOMAIN], "Unable to replace", id="not-mac-children"
        ),
        pytest.param(
            DEVICE_ID, 1, [DOMAIN, "other"], None, id="not-mac-no-children-other-domain"
        ),
        pytest.param(
            DEVICE_ID,
            3,
            [DOMAIN, "other"],
            "Unable to replace",
            id="not-mac-children-other-domain",
        ),
    ],
)
async def test_unlink_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    device_id,
    id_count,
    domains,
    expected_message,
) -> None:
    """Test for unlinking child device ids."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**CREATE_ENTRY_DATA_LEGACY},
        entry_id="123456",
        unique_id="any",
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    # Generate list of test identifiers
    test_identifiers = [
        (domain, f"{device_id}{"" if i == 0 else f"_000{i}"}")
        for i in range(id_count)
        for domain in domains
    ]
    update_msg_fragment = "identifiers for device dummy (hs300):"
    update_msg = f"{expected_message} {update_msg_fragment}" if expected_message else ""

    # Expected identifiers should include all other domains or all the newer non-mac device ids
    # or just the parent mac device id
    expected_identifiers = [
        (domain, device_id)
        for domain, device_id in test_identifiers
        if domain != DOMAIN
        or device_id.startswith(DEVICE_ID)
        or device_id == DEVICE_ID_MAC
    ]

    device_registry.async_get_or_create(
        config_entry_id="123456",
        connections={
            (dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS),
        },
        identifiers=set(test_identifiers),
        model="hs300",
        name="dummy",
    )
    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    assert device_entries[0].connections == {
        (dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS),
    }
    assert device_entries[0].identifiers == set(test_identifiers)

    with patch("homeassistant.components.tplink.CONF_CONFIG_ENTRY_MINOR_VERSION", 3):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    assert device_entries[0].connections == {(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)}

    assert device_entries[0].identifiers == set(expected_identifiers)
    assert entry.version == 1
    assert entry.minor_version == 3

    assert update_msg in caplog.text
    assert "Migration to version 1.3 complete" in caplog.text


async def test_move_credentials_hash(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test credentials hash moved to parent.

    As async_setup_entry will succeed the hash on the parent is updated
    from the device.
    """
    device_config = {
        **DEVICE_CONFIG_DICT_KLAP,
        "credentials_hash": "theHash",
    }
    entry_data = {**CREATE_ENTRY_DATA_KLAP, CONF_DEVICE_CONFIG: device_config}

    entry = MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data=entry_data,
        entry_id="123456",
        unique_id=MAC_ADDRESS,
        version=1,
        minor_version=3,
    )
    assert entry.data[CONF_DEVICE_CONFIG][CONF_CREDENTIALS_HASH] == "theHash"
    entry.add_to_hass(hass)

    async def _connect(config):
        config.credentials_hash = "theNewHash"
        return _mocked_device(device_config=config, credentials_hash="theNewHash")

    with (
        patch("homeassistant.components.tplink.Device.connect", new=_connect),
        patch("homeassistant.components.tplink.PLATFORMS", []),
        patch("homeassistant.components.tplink.CONF_CONFIG_ENTRY_MINOR_VERSION", 4),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.minor_version == 4
    assert entry.state is ConfigEntryState.LOADED
    assert CONF_CREDENTIALS_HASH not in entry.data[CONF_DEVICE_CONFIG]
    assert CONF_CREDENTIALS_HASH in entry.data
    # Gets the new hash from the successful connection.
    assert entry.data[CONF_CREDENTIALS_HASH] == "theNewHash"
    assert "Migration to version 1.4 complete" in caplog.text


async def test_move_credentials_hash_auth_error(
    hass: HomeAssistant,
) -> None:
    """Test credentials hash moved to parent.

    If there is an auth error it should be deleted after migration
    in async_setup_entry.
    """
    device_config = {
        **DEVICE_CONFIG_DICT_KLAP,
        "credentials_hash": "theHash",
    }
    entry_data = {**CREATE_ENTRY_DATA_KLAP, CONF_DEVICE_CONFIG: device_config}

    entry = MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data=entry_data,
        unique_id=MAC_ADDRESS,
        version=1,
        minor_version=3,
    )
    assert entry.data[CONF_DEVICE_CONFIG][CONF_CREDENTIALS_HASH] == "theHash"

    with (
        patch(
            "homeassistant.components.tplink.Device.connect",
            side_effect=AuthenticationError,
        ),
        patch("homeassistant.components.tplink.PLATFORMS", []),
        patch("homeassistant.components.tplink.CONF_CONFIG_ENTRY_MINOR_VERSION", 4),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.minor_version == 4
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert CONF_CREDENTIALS_HASH not in entry.data[CONF_DEVICE_CONFIG]
    # Auth failure deletes the hash
    assert CONF_CREDENTIALS_HASH not in entry.data


async def test_move_credentials_hash_other_error(
    hass: HomeAssistant,
) -> None:
    """Test credentials hash moved to parent.

    When there is a KasaException the same hash should still be on the parent
    at the end of the test.
    """
    device_config = {
        **DEVICE_CONFIG_DICT_KLAP,
        "credentials_hash": "theHash",
    }
    entry_data = {**CREATE_ENTRY_DATA_KLAP, CONF_DEVICE_CONFIG: device_config}

    entry = MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data=entry_data,
        unique_id=MAC_ADDRESS,
        version=1,
        minor_version=3,
    )
    assert entry.data[CONF_DEVICE_CONFIG][CONF_CREDENTIALS_HASH] == "theHash"

    with (
        patch(
            "homeassistant.components.tplink.Device.connect", side_effect=KasaException
        ),
        patch("homeassistant.components.tplink.PLATFORMS", []),
        patch("homeassistant.components.tplink.CONF_CONFIG_ENTRY_MINOR_VERSION", 4),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.minor_version == 4
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert CONF_CREDENTIALS_HASH not in entry.data[CONF_DEVICE_CONFIG]
    assert CONF_CREDENTIALS_HASH in entry.data
    assert entry.data[CONF_CREDENTIALS_HASH] == "theHash"


async def test_credentials_hash(
    hass: HomeAssistant,
) -> None:
    """Test credentials_hash used to call connect."""
    entry_data = {
        **CREATE_ENTRY_DATA_KLAP,
        CONF_CREDENTIALS_HASH: "theHash",
    }

    entry = MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data=entry_data,
        unique_id=MAC_ADDRESS,
    )

    async def _connect(config):
        config.credentials_hash = "theHash"
        return _mocked_device(device_config=config, credentials_hash="theHash")

    with (
        patch("homeassistant.components.tplink.PLATFORMS", []),
        patch("homeassistant.components.tplink.Device.connect", new=_connect),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert CONF_CREDENTIALS_HASH in entry.data
    assert entry.data[CONF_CREDENTIALS_HASH] == "theHash"


async def test_credentials_hash_auth_error(
    hass: HomeAssistant,
) -> None:
    """Test credentials_hash is deleted after an auth failure."""
    entry_data = {
        **CREATE_ENTRY_DATA_KLAP,
        CONF_CREDENTIALS_HASH: "theHash",
    }

    entry = MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data=entry_data,
        unique_id=MAC_ADDRESS,
    )

    with (
        patch("homeassistant.components.tplink.PLATFORMS", []),
        patch(
            "homeassistant.components.tplink.async_create_clientsession",
            return_value="Foo",
        ),
        patch(
            "homeassistant.components.tplink.Device.connect",
            side_effect=AuthenticationError,
        ) as connect_mock,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    expected_config = DeviceConfig.from_dict(
        {**DEVICE_CONFIG_DICT_KLAP, "credentials_hash": "theHash"}
    )
    expected_config.uses_http = False
    expected_config.http_client = "Foo"
    connect_mock.assert_called_with(config=expected_config)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert CONF_CREDENTIALS_HASH not in entry.data


@pytest.mark.parametrize(
    ("device_config", "expected_entry_data", "credentials_hash"),
    [
        pytest.param(
            DEVICE_CONFIG_KLAP, CREATE_ENTRY_DATA_KLAP, CREDENTIALS_HASH_KLAP, id="KLAP"
        ),
        pytest.param(
            DEVICE_CONFIG_AES, CREATE_ENTRY_DATA_AES, CREDENTIALS_HASH_AES, id="AES"
        ),
        pytest.param(DEVICE_CONFIG_LEGACY, CREATE_ENTRY_DATA_LEGACY, None, id="Legacy"),
    ],
)
async def test_migrate_remove_device_config(
    hass: HomeAssistant,
    mock_connect: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    device_config: DeviceConfig,
    expected_entry_data: dict[str, Any],
    credentials_hash: str,
) -> None:
    """Test credentials hash moved to parent.

    As async_setup_entry will succeed the hash on the parent is updated
    from the device.
    """
    OLD_CREATE_ENTRY_DATA = {
        CONF_HOST: expected_entry_data[CONF_HOST],
        CONF_ALIAS: ALIAS,
        CONF_MODEL: MODEL,
        CONF_DEVICE_CONFIG: {
            k: v for k, v in device_config.to_dict().items() if k != "credentials"
        },
    }

    entry = MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data=OLD_CREATE_ENTRY_DATA,
        entry_id="123456",
        unique_id=MAC_ADDRESS,
        version=1,
        minor_version=4,
    )
    entry.add_to_hass(hass)

    async def _connect(config):
        config.credentials_hash = credentials_hash
        config.aes_keys = expected_entry_data.get(CONF_AES_KEYS)
        return _mocked_device(device_config=config, credentials_hash=credentials_hash)

    with (
        patch("homeassistant.components.tplink.Device.connect", new=_connect),
        patch("homeassistant.components.tplink.PLATFORMS", []),
        patch(
            "homeassistant.components.tplink.async_create_clientsession",
            return_value="Foo",
        ),
        patch("homeassistant.components.tplink.CONF_CONFIG_ENTRY_MINOR_VERSION", 5),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.minor_version == 5
    assert entry.state is ConfigEntryState.LOADED
    assert CONF_DEVICE_CONFIG not in entry.data
    assert entry.data == expected_entry_data

    assert "Migration to version 1.5 complete" in caplog.text
