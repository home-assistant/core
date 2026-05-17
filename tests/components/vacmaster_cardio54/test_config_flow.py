"""Tests for the Vacmaster Cardio54 config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.radio_frequency import DATA_COMPONENT
from homeassistant.components.vacmaster_cardio54.const import (
    CONF_DEVICE_ID,
    CONF_TRANSMITTER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity

# Deterministic random.getrandbits return value used to pin the auto-ID.
FIXED_DEVICE_ID = 0xABCDE


def _transmitter_registry_id(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> str:
    """Return the entity-registry ID (NOT entity_id) of the mock transmitter."""
    entry = er.async_get(hass).async_get(mock_rf_entity.entity_id)
    assert entry is not None
    return entry.id


def _transmitter_entity_id(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> str:
    """Return the entity_id (e.g. radio_frequency.test_rf_transmitter)."""
    return mock_rf_entity.entity_id


async def test_user_flow_happy_path(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """User -> pair -> test -> finish creates the entry with the auto-ID."""
    registry_id = _transmitter_registry_id(hass, mock_rf_entity)
    entity_id = _transmitter_entity_id(hass, mock_rf_entity)

    with patch(
        "homeassistant.components.vacmaster_cardio54.config_flow.random.getrandbits",
        return_value=FIXED_DEVICE_ID,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TRANSMITTER: entity_id}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"

        # Submit the pair step -> burst is sent, then we're on the test step
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # After the pair burst the flow shows the test menu.
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "test"

    # User confirms the fan reacted.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Vacmaster Cardio54"
    assert result["data"] == {
        CONF_TRANSMITTER: registry_id,
        CONF_DEVICE_ID: FIXED_DEVICE_ID,
    }
    assert result["result"].unique_id == f"{registry_id}_{FIXED_DEVICE_ID:05X}"

    # The mock transmitter should have seen two sends: pair burst + test burst.
    assert len(mock_rf_entity.send_command_calls) == 2


async def test_user_flow_pair_send_failure(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """If the pair burst fails the flow shows the send_failed menu."""
    entity_id = _transmitter_entity_id(hass, mock_rf_entity)

    with patch(
        "homeassistant.components.vacmaster_cardio54.config_flow.random.getrandbits",
        return_value=FIXED_DEVICE_ID,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TRANSMITTER: entity_id}
        )
        with patch(
            "homeassistant.components.vacmaster_cardio54.config_flow.async_send_command",
            side_effect=HomeAssistantError("transmitter offline"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {}
            )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "send_failed"


async def test_user_flow_recover_after_pair_failure(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """Retry from send_failed runs the pair step again and can succeed."""
    entity_id = _transmitter_entity_id(hass, mock_rf_entity)

    with patch(
        "homeassistant.components.vacmaster_cardio54.config_flow.random.getrandbits",
        return_value=FIXED_DEVICE_ID,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TRANSMITTER: entity_id}
        )
        with patch(
            "homeassistant.components.vacmaster_cardio54.config_flow.async_send_command",
            side_effect=HomeAssistantError("transmitter offline"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {}
            )
        # Retry — now the transmitter accepts.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "retry"}
        )
        # async_step_retry routes us back into the pair form; submit it.
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "test"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "finish"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_test_send_failure(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """If the post-pair test send fails we land on send_failed too."""
    entity_id = _transmitter_entity_id(hass, mock_rf_entity)

    # Let the pair burst go through but break the test-step send.
    real_send = mock_rf_entity.async_send_command
    call_count = {"n": 0}

    async def selective_failure(command):
        call_count["n"] += 1
        if call_count["n"] == 1:
            await real_send(command)
            return
        raise HomeAssistantError("transmitter glitched")

    with (
        patch(
            "homeassistant.components.vacmaster_cardio54.config_flow.random.getrandbits",
            return_value=FIXED_DEVICE_ID,
        ),
        patch.object(
            mock_rf_entity, "async_send_command", side_effect=selective_failure
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TRANSMITTER: entity_id}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "send_failed"


async def test_user_flow_no_transmitters(hass: HomeAssistant) -> None:
    """Aborts cleanly when the radio_frequency integration isn't loaded yet."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_transmitters"


async def test_user_flow_no_compatible_transmitters(
    hass: HomeAssistant, init_radio_frequency: None
) -> None:
    """Aborts when the only transmitter doesn't support 433.92 MHz OOK."""
    # Add a transmitter that only covers 868 MHz.
    entity = MockRadioFrequencyEntity(
        "incompatible_tx", frequency_ranges=[(868_000_000, 868_500_000)]
    )
    await hass.data[DATA_COMPONENT].async_add_entities([entity])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_compatible_transmitters"


async def test_reconfigure_changes_transmitter(
    hass: HomeAssistant,
    init_radio_frequency: None,
    init_vacmaster_cardio54: MockConfigEntry,
) -> None:
    """Reconfigure can move the fan to a second transmitter, keeping its ID."""
    # Add a second compatible transmitter.
    second = MockRadioFrequencyEntity("second_tx")
    await hass.data[DATA_COMPONENT].async_add_entities([second])
    second_entity_id = _transmitter_entity_id(hass, second)
    second_registry_id = _transmitter_registry_id(hass, second)

    result = await init_vacmaster_cardio54.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TRANSMITTER: second_entity_id}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_vacmaster_cardio54.data[CONF_TRANSMITTER] == second_registry_id
    # Device ID is preserved across reconfigure.
    assert init_vacmaster_cardio54.data[CONF_DEVICE_ID] == FIXED_DEVICE_ID


async def test_reconfigure_collision_aborts(
    hass: HomeAssistant,
    init_radio_frequency: None,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> None:
    """Reconfigure aborts when target tx+device_id is already used by another entry."""
    # First entry on transmitter A with our fixed device ID.
    primary_registry_id = _transmitter_registry_id(hass, mock_rf_entity)
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="Existing",
        data={
            CONF_TRANSMITTER: primary_registry_id,
            CONF_DEVICE_ID: FIXED_DEVICE_ID,
        },
        unique_id=f"{primary_registry_id}_{FIXED_DEVICE_ID:05X}",
    )
    existing.add_to_hass(hass)

    # Second entry on a different transmitter, also using our fixed ID --
    # then reconfigure it onto the first transmitter -> should collide.
    second = MockRadioFrequencyEntity("second_tx")
    await hass.data[DATA_COMPONENT].async_add_entities([second])
    second_registry_id = _transmitter_registry_id(hass, second)
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Other",
        data={
            CONF_TRANSMITTER: second_registry_id,
            CONF_DEVICE_ID: FIXED_DEVICE_ID,
        },
        unique_id=f"{second_registry_id}_{FIXED_DEVICE_ID:05X}",
    )
    other.add_to_hass(hass)

    result = await other.start_reconfigure_flow(hass)
    primary_entity_id = _transmitter_entity_id(hass, mock_rf_entity)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TRANSMITTER: primary_entity_id}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_no_transmitters_aborts(
    hass: HomeAssistant, init_vacmaster_cardio54: MockConfigEntry
) -> None:
    """Reconfigure aborts cleanly if radio_frequency is gone."""
    # Patch ``async_get_transmitters`` to raise the same ``HomeAssistantError``
    # it would emit when the ``radio_frequency`` component is unloaded. This
    # tests the abort branch without poking at HA internals (the previous
    # approach of removing the component from ``hass.config.components`` and
    # ``hass.data`` was fragile across HA refactors).
    with patch(
        "homeassistant.components.vacmaster_cardio54.config_flow.async_get_transmitters",
        side_effect=HomeAssistantError("radio_frequency unloaded"),
    ):
        result = await init_vacmaster_cardio54.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_transmitters"


async def test_reconfigure_no_compatible_transmitters_aborts(
    hass: HomeAssistant,
    init_radio_frequency: None,
    init_vacmaster_cardio54: MockConfigEntry,
) -> None:
    """If no remaining tx supports our frequency, reconfigure aborts."""
    # Drop the default 433 MHz mock and leave only an 868 MHz one.
    await hass.data[DATA_COMPONENT].async_remove_entity(
        next(iter(hass.data[DATA_COMPONENT].entities)).entity_id
    )
    only_868 = MockRadioFrequencyEntity(
        "only_868", frequency_ranges=[(868_000_000, 868_500_000)]
    )
    await hass.data[DATA_COMPONENT].async_add_entities([only_868])

    result = await init_vacmaster_cardio54.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_compatible_transmitters"


async def test_user_flow_generator_skips_used_device_ids(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """``_generate_device_id`` retries until it finds an unused 20-bit ID.

    Covers the ``while ... continue`` branch in config_flow.py — pre-register
    one entry with a known ID, force the random source to hand back that
    same ID first and a fresh one second, and verify the second value is
    what ends up in the new entry.
    """
    entity_id = _transmitter_entity_id(hass, mock_rf_entity)
    registry_id = _transmitter_registry_id(hass, mock_rf_entity)

    colliding_id = 0x11111
    free_id = 0x22222
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="Existing Cardio54",
        data={CONF_TRANSMITTER: registry_id, CONF_DEVICE_ID: colliding_id},
        unique_id=f"{registry_id}_{colliding_id:05X}",
    )
    existing.add_to_hass(hass)

    with patch(
        "homeassistant.components.vacmaster_cardio54.config_flow.random.getrandbits",
        side_effect=[colliding_id, free_id],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TRANSMITTER: entity_id}
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "finish"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == free_id
    assert result["result"].unique_id == f"{registry_id}_{free_id:05X}"


async def test_device_id_generator_raises_when_exhausted(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """``_generate_device_id`` bails after 1000 retries instead of hanging.

    Pathological safeguard for the case where the 20-bit ID space on a
    single transmitter is effectively exhausted — without the bounded
    retry the ``while`` loop would block the event loop forever.
    """
    from homeassistant.components.vacmaster_cardio54.config_flow import (
        VacmasterCardio54ConfigFlow,
    )

    registry_id = _transmitter_registry_id(hass, mock_rf_entity)
    colliding_id = 0x11111
    MockConfigEntry(
        domain=DOMAIN,
        title="Existing Cardio54",
        data={CONF_TRANSMITTER: registry_id, CONF_DEVICE_ID: colliding_id},
        unique_id=f"{registry_id}_{colliding_id:05X}",
    ).add_to_hass(hass)

    flow = VacmasterCardio54ConfigFlow()
    flow.hass = hass

    with (
        patch(
            "homeassistant.components.vacmaster_cardio54.config_flow.random.getrandbits",
            return_value=colliding_id,
        ),
        pytest.raises(HomeAssistantError, match="Could not allocate"),
    ):
        flow._generate_device_id(registry_id)
