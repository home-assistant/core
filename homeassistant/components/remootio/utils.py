"""Utility methods for the Remootio integration."""
from __future__ import annotations

import asyncio
import logging
from logging import Logger

from aioremootio import ConnectionOptions, LoggerConfiguration, RemootioClient
from aioremootio.enums import State
import async_timeout

from homeassistant import core
from homeassistant.helpers import aiohttp_client

from .const import EXPECTED_MINIMUM_API_VERSION, REMOOTIO_DELAY, REMOOTIO_TIMEOUT
from .exceptions import (
    UnsupportedRemootioApiVersionError,
    UnsupportedRemootioDeviceError,
)

_LOGGER = logging.getLogger(__name__)


async def _wait_for_connected(remootio_client: RemootioClient) -> bool:
    while not remootio_client.connected:
        await asyncio.sleep(REMOOTIO_DELAY)

    return remootio_client.connected


async def _check_api_version(remootio_client: RemootioClient) -> None:
    """Check whether the by the given client represented Remootio device uses a supported API version."""
    api_version: int = remootio_client.api_version
    if api_version < EXPECTED_MINIMUM_API_VERSION:
        raise UnsupportedRemootioApiVersionError


async def _check_sensor_installed(
    remootio_client: RemootioClient, raise_error: bool = True
) -> None:
    """Check whether the by the given client represented Remootio device has a sensor installed."""
    if remootio_client.state == State.NO_SENSOR_INSTALLED:
        if raise_error:
            raise UnsupportedRemootioDeviceError

        _LOGGER.error(
            "Your Remootio device isn't supported, possibly because it hasn't a sensor installed. Host [%s]",
            remootio_client.host,
        )


async def get_serial_number(
    hass: core.HomeAssistant, connection_options: ConnectionOptions, logger: Logger
) -> str:
    """Connect to a Remootio device based on the given connection options and retrieve its serial number."""
    result: str = ""

    async with async_timeout.timeout(REMOOTIO_TIMEOUT):
        async with RemootioClient(
            connection_options,
            aiohttp_client.async_get_clientsession(hass),
            LoggerConfiguration(logger=logger),
        ) as remootio_client:
            if await _wait_for_connected(remootio_client):
                await _check_sensor_installed(remootio_client)
                await _check_api_version(remootio_client)

                result = remootio_client.serial_number

    return result


async def create_client(
    hass: core.HomeAssistant,
    connection_options: ConnectionOptions,
    logger: Logger,
    expected_serial_number: str | None = None,
) -> RemootioClient:
    """Create an Remootio client based on the given data."""
    result: RemootioClient = None

    async with async_timeout.timeout(REMOOTIO_TIMEOUT):
        result = await RemootioClient(
            connection_options,
            aiohttp_client.async_get_clientsession(hass),
            LoggerConfiguration(logger=logger),
        )

        if await _wait_for_connected(result):
            await _check_sensor_installed(result, False)
            await _check_api_version(result)

            if expected_serial_number is not None:
                serial_number: str = result.serial_number
                assert (
                    expected_serial_number == serial_number
                ), f"Serial number of the Remootio device isn't the expected. Actual [{serial_number}] Expected [{expected_serial_number}]"

    return result
