"""Tests for component test fixtures."""

from collections.abc import Callable

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized, UnknownUser

from . import conftest as components_conftest

from tests.common import QualityScaleStatus


@pytest.mark.parametrize(
    "exception_type",
    [
        pytest.param(Unauthorized, id="unauthorized"),
        pytest.param(UnknownUser, id="unknown-user"),
    ],
)
async def test_authorization_errors_do_not_require_integration_translations(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    exception_type: Callable[[], Unauthorized],
) -> None:
    """Test core authorization errors do not require integration translations."""
    monkeypatch.setattr(
        components_conftest,
        "_get_request_quality_scale",
        lambda *_: QualityScaleStatus.DONE,
    )
    translation_errors: dict[str, str] = {}

    await components_conftest._check_exception_translation(
        hass,
        exception_type(),
        translation_errors,
        request,
        set(),
    )

    assert not translation_errors
