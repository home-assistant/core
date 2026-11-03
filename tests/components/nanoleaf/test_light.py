"""Tests for the Nanoleaf light platform."""

from unittest.mock import AsyncMock, patch

from aionanoleaf2 import (
    AuthError,
    EndpointNotFoundError,
    InvalidEffect,
    InvalidEmersion,
    InvalidResponseError,
    InvalidToken,
    NanoleafConnectionError,
    NanoleafError,
    NanoleafTimeoutError,
    NoAuthToken,
    Unavailable,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.nanoleaf.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import get_reauth_flows, setup_integration

NANOLEAF_ERRORS = [
    pytest.param(Unavailable("unavailable"), id="unavailable"),
    pytest.param(NanoleafConnectionError("connection"), id="connection"),
    pytest.param(NanoleafTimeoutError("timeout"), id="timeout"),
    pytest.param(InvalidResponseError("response"), id="invalid_response"),
    pytest.param(EndpointNotFoundError("state"), id="endpoint_not_found"),
    pytest.param(NanoleafError("generic"), id="generic"),
]

AUTH_ERRORS = [
    pytest.param(InvalidToken("invalid"), id="invalid_token"),
    pytest.param(AuthError("auth"), id="auth_error"),
    pytest.param(NoAuthToken("missing"), id="no_token"),
]


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.nanoleaf.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_turning_on_or_off_writes_state(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test turning on or off the light writes the state."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.nanoleaf").attributes[ATTR_EFFECT_LIST] == [
        "Rainbow",
        "Sunset",
        "Nemo",
    ]

    mock_nanoleaf.effects_list = ["Rainbow", "Sunset", "Nemo", "Something Else"]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: "light.nanoleaf",
        },
        blocking=True,
    )
    assert hass.states.get("light.nanoleaf").attributes[ATTR_EFFECT_LIST] == [
        "Rainbow",
        "Sunset",
        "Nemo",
        "Something Else",
    ]


@pytest.mark.parametrize(
    ("effect", "expected_effect"),
    [
        ("", None),
        ("*Solid*", None),
        ("Rainbow", "Rainbow"),
    ],
)
async def test_effect(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    effect: str,
    expected_effect: str | None,
) -> None:
    """Test the current effect."""
    mock_nanoleaf.is_on = True
    mock_nanoleaf.effect = effect

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.nanoleaf")
    assert state is not None
    assert state.attributes.get(ATTR_EFFECT) == expected_effect


async def _call(hass: HomeAssistant, service: str, **data: object) -> None:
    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "light.nanoleaf", **data},
        blocking=True,
    )


@pytest.mark.parametrize("error", NANOLEAF_ERRORS)
@pytest.mark.parametrize(
    ("service", "method"),
    [(SERVICE_TURN_ON, "turn_on"), (SERVICE_TURN_OFF, "turn_off")],
)
async def test_service_maps_nanoleaf_errors(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
    error: NanoleafError,
) -> None:
    """Test library errors become a Home Assistant error without reauth."""
    await setup_integration(hass, mock_config_entry)
    getattr(mock_nanoleaf, method).side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call(hass, service)
    await hass.async_block_till_done()

    assert not isinstance(exc_info.value, ServiceValidationError)
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "cannot_connect"
    assert exc_info.value.__cause__ is error
    assert not get_reauth_flows(hass, mock_config_entry)


@pytest.mark.parametrize("error", AUTH_ERRORS)
@pytest.mark.parametrize(
    ("service", "method"),
    [(SERVICE_TURN_ON, "turn_on"), (SERVICE_TURN_OFF, "turn_off")],
)
async def test_service_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
    error: NanoleafError,
) -> None:
    """Test a rejected token raises a Home Assistant error and starts reauth."""
    await setup_integration(hass, mock_config_entry)
    getattr(mock_nanoleaf, method).side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call(hass, service)
    await hass.async_block_till_done()

    assert exc_info.value.translation_key == "invalid_token"
    assert exc_info.value.__cause__ is error
    assert len(get_reauth_flows(hass, mock_config_entry)) == 1


async def test_turn_on_unknown_effect_is_a_validation_error(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an effect that is not in the effect list is rejected."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await _call(hass, SERVICE_TURN_ON, **{ATTR_EFFECT: "Does Not Exist"})

    mock_nanoleaf.set_effect.assert_not_called()
    assert not get_reauth_flows(hass, mock_config_entry)


async def test_turn_on_effect_rejected_by_library_is_a_validation_error(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test InvalidEffect from the library maps to a validation error."""
    await setup_integration(hass, mock_config_entry)
    mock_nanoleaf.set_effect.side_effect = InvalidEffect

    with pytest.raises(ServiceValidationError) as exc_info:
        await _call(hass, SERVICE_TURN_ON, **{ATTR_EFFECT: "Rainbow"})

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "effect_not_supported"
    assert isinstance(exc_info.value.__cause__, InvalidEffect)


async def test_turn_on_known_effect(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a valid effect is forwarded to the device."""
    await setup_integration(hass, mock_config_entry)

    await _call(hass, SERVICE_TURN_ON, **{ATTR_EFFECT: "Sunset"})

    mock_nanoleaf.set_effect.assert_awaited_once_with("Sunset")


EMERSION_MODES = ["1D", "2D", "3D", "4D"]


async def test_effect_list_includes_emersion_modes(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Screen Mirroring modes of a Nanoleaf 4D are offered as effects."""
    mock_nanoleaf.emersion_list = EMERSION_MODES

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.nanoleaf").attributes[ATTR_EFFECT_LIST] == [
        "Rainbow",
        "Sunset",
        "Nemo",
        *EMERSION_MODES,
    ]


async def test_effect_list_does_not_duplicate_effect_named_like_a_mode(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a regular effect named like a mode is listed once."""
    mock_nanoleaf.effects_list = ["Rainbow", "2D"]
    mock_nanoleaf.emersion_list = EMERSION_MODES

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.nanoleaf").attributes[ATTR_EFFECT_LIST] == [
        "Rainbow",
        "2D",
        "1D",
        "3D",
        "4D",
    ]


@pytest.mark.parametrize(
    ("selected_emersion", "expected_effect"),
    [("3D", "3D"), (None, None)],
)
async def test_effect_reports_active_emersion_mode(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    selected_emersion: str | None,
    expected_effect: str | None,
) -> None:
    """Test the active Screen Mirroring mode is reported as the effect."""
    mock_nanoleaf.is_on = True
    mock_nanoleaf.effect = "*Emersion*"
    mock_nanoleaf.emersion_list = EMERSION_MODES
    mock_nanoleaf.selected_emersion = selected_emersion

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("light.nanoleaf")
    assert state is not None
    assert state.attributes.get(ATTR_EFFECT) == expected_effect


async def test_turn_on_emersion_mode(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a Screen Mirroring mode is activated instead of a regular effect."""
    mock_nanoleaf.emersion_list = EMERSION_MODES
    await setup_integration(hass, mock_config_entry)

    await _call(hass, SERVICE_TURN_ON, **{ATTR_EFFECT: "2D"})

    mock_nanoleaf.set_emersion.assert_awaited_once_with("2D")
    mock_nanoleaf.set_effect.assert_not_called()


async def test_turn_on_emersion_mode_is_rejected_without_screen_mirroring(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a mode name is not accepted by devices without Screen Mirroring."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await _call(hass, SERVICE_TURN_ON, **{ATTR_EFFECT: "2D"})

    mock_nanoleaf.set_emersion.assert_not_called()
    mock_nanoleaf.set_effect.assert_not_called()


async def test_turn_on_emersion_mode_rejected_by_library_is_a_validation_error(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test InvalidEmersion from the library maps to a validation error."""
    mock_nanoleaf.emersion_list = EMERSION_MODES
    await setup_integration(hass, mock_config_entry)
    mock_nanoleaf.set_emersion.side_effect = InvalidEmersion

    with pytest.raises(ServiceValidationError) as exc_info:
        await _call(hass, SERVICE_TURN_ON, **{ATTR_EFFECT: "4D"})

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "effect_not_supported"
    assert isinstance(exc_info.value.__cause__, InvalidEmersion)
