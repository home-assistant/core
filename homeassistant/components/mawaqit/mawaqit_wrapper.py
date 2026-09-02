"""Provides a wrapper for interacting with the MAWAQIT API."""

from mawaqit import AsyncMawaqitClient

from .types import MawaqitMosqueData


async def all_mosques_neighborhood(
    client: AsyncMawaqitClient,
) -> list[MawaqitMosqueData]:
    """Return the mosques around the coordinates configured on the client."""
    response = await client.all_mosques_neighborhood()
    return [MawaqitMosqueData.from_dict(mosque) for mosque in response]
