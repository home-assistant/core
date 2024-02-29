"""Test the cloud assist pipeline."""
import pytest

from homeassistant.components.cloud.assist_pipeline import (
    async_migrate_cloud_pipeline_engine,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


async def test_migrate_pipeline_invalid_platform(hass: HomeAssistant) -> None:
    """Test migrate pipeline with invalid platform."""
    with pytest.raises(ValueError):
        await async_migrate_cloud_pipeline_engine(
            hass, Platform.BINARY_SENSOR, "test-engine-id"
        )
