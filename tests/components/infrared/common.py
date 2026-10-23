"""Compatibility imports for the Home Assistant pytest helpers."""

# ruff: noqa: PLC0414

from pytest_homeassistant.components.infrared.common import (
    DATA_COMPONENT as DATA_COMPONENT,
    DOMAIN as DOMAIN,
    HomeAssistant as HomeAssistant,
    InfraredCommand as InfraredCommand,
    InfraredEmitterEntity as InfraredEmitterEntity,
    InfraredEntity as InfraredEntity,
    InfraredReceiverEntity as InfraredReceiverEntity,
    MockInfraredEmitterEntity as MockInfraredEmitterEntity,
    MockInfraredEntity as MockInfraredEntity,
    MockInfraredReceiverEntity as MockInfraredReceiverEntity,
    async_setup_component as async_setup_component,
    init_infrared_fixture_helper as init_infrared_fixture_helper,
    mock_infrared_emitter_entity_fixture_helper as mock_infrared_emitter_entity_fixture_helper,
    mock_infrared_receiver_entity_fixture_helper as mock_infrared_receiver_entity_fixture_helper,
)
