"""Helper functions for HomeWizard Energy"""
from __future__ import annotations
import asyncio
import async_timeout

from aiohwenergy import HomeWizardEnergy
from aiohwenergy.errors import RequestError
from homeassistant.exceptions import ConfigEntryNotReady

from .const import LOGGER


async def async_validate_connection(api: HomeWizardEnergy) -> bool:
    initialized = False
    try:
        with async_timeout.timeout(10):
            await api.initialize()
            initialized = True

    except (asyncio.TimeoutError, RequestError):
        LOGGER.error(
            "Error connecting to the device at %s",
            api._host,
        )
        raise ConfigEntryNotReady

    except Exception:  # pylint: disable=broad-except
        LOGGER.exception(
            "Unknown error connecting with device at %s",
            api._host["host"],
        )
        return False

    finally:
        if not initialized:
            await api.close()

    return initialized
