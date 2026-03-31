"""Helper methods for calling the Electrolux API."""

import logging

from electrolux_group_developer_sdk.client.appliance_client import ApplianceClient
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.client_exception import (
    ApplianceClientException,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def fetch_appliance_data(client: ApplianceClient) -> list[ApplianceData]:
    """Helper method to retrieve all the appliances data from the Electrolux APIs."""
    try:
        appliances = await client.get_appliance_data()
    except ApplianceClientException as e:
        appliances = []
        _LOGGER.warning("Failed to get appliances: %s", e)

    # Filter out appliances where details or state is None
    return [
        appliance
        for appliance in appliances
        if appliance.details is not None and appliance.state is not None
    ]
