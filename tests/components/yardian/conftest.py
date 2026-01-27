"""Common fixtures for the Yardian tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pyyardian import OperationInfo, YardianDeviceState

from homeassistant.components.yardian import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import translation as translation_helper

from tests.common import MockConfigEntry

_STRINGS_PATH = (
    Path(__file__).resolve().parents[3]
    / "homeassistant/components/yardian/strings.json"
)
_ENTITY_TRANSLATIONS: dict[str, str] = {}


def _build_entity_translations() -> dict[str, str]:
    """Flatten entity strings into translation overrides."""
    strings: dict[str, Any] = json.loads(_STRINGS_PATH.read_text())
    translations: dict[str, str] = {}
    for platform, entries in strings.get("entity", {}).items():
        for key, details in entries.items():
            if name := details.get("name"):
                translations[f"component.{DOMAIN}.entity.{platform}.{key}.name"] = name
            if states := details.get("state"):
                for state_key, state_value in states.items():
                    translations[
                        f"component.{DOMAIN}.entity.{platform}.{key}.state.{state_key}"
                    ] = state_value
    return translations


_ENTITY_TRANSLATIONS = _build_entity_translations()


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.yardian.async_setup_entry", return_value=True
    ) as patched_setup_entry:
        yield patched_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Provide a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="yid123",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_ACCESS_TOKEN: "abc",
            CONF_NAME: "Yardian",
            "yid": "yid123",
            "model": "PRO1902",
            "serialNumber": "SN1",
        },
        title="Yardian Smart Sprinkler",
    )


@pytest.fixture
def mock_yardian_client() -> Generator[AsyncMock]:
    """Mock the Yardian client used by the integration and config flow."""
    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient", autospec=True
        ) as client_cls,
        patch(
            "homeassistant.components.yardian.config_flow.AsyncYardianClient",
            autospec=True,
        ) as flow_client_cls,
    ):
        client = client_cls.return_value
        flow_client_cls.return_value = client

        client.fetch_device_state.return_value = YardianDeviceState(
            zones=[["Zone 1", 1], ["Zone 2", 0]],
            active_zones={0},
        )
        client.fetch_oper_info.return_value = OperationInfo(
            iRainDelay=3600,
            iSensorDelay=5,
            iWaterHammerDuration=2,
            iStandby=1,
            fFreezePrevent=1,
        )

        yield client


@pytest.fixture
def sensor_platform_only() -> Generator[None]:
    """Limit the integration setup to the sensor platform for faster tests."""
    with patch("homeassistant.components.yardian.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.fixture(autouse=True)
def yardian_translation_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject English translations without committing generated en.json files."""

    original_async_get_translations = translation_helper.async_get_translations

    async def _async_get_translations(
        hass: HomeAssistant | None,
        language: str,
        category: str,
        integrations: list[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, str]:
        if hass is None:
            return await original_async_get_translations(
                hass, language, category, integrations, config_flow
            )

        translations = await original_async_get_translations(
            hass, language, category, integrations, config_flow
        )

        if language != "en" or category != "entity":
            return translations

        missing_keys = _ENTITY_TRANSLATIONS.keys() - translations.keys()
        if not missing_keys:
            return translations

        enriched = translations.copy()
        for key in missing_keys:
            enriched[key] = _ENTITY_TRANSLATIONS[key]

        return enriched

    monkeypatch.setattr(
        translation_helper, "async_get_translations", _async_get_translations
    )
