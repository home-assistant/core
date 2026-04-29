"""Tests for the OMIE - Spain and Portugal electricity prices integration."""

from datetime import date

from pyomie.model import OMIEResults


def price_enc(country: int, day: int, hour: int, minute: int) -> float:
    """Encode the given data into a price.

    Format is CCDDhhmm000. Examples:
    -  351 15 01 15 000 for CC=351 (Portugal), DD=15 (day of month), hh=01 (1 am), mm=15.
    -   34 16 23 00 000 for CC=34 (Spain), DD=16 (day of month), hh=23 (11 pm), mm=00.

    This allows us to make assertions in tests without having
    to look up the expected values in large datasets.
    """
    return country * 10**9 + day * 10**7 + hour * 10**5 + minute * 10**3


def spot_price_fetcher(spot_price_data: dict):
    """Return spot price fetcher for any data dictionary.

    Args:
        spot_price_data: Dictionary mapping ISO date strings to mock results

    """
    data_by_date = {
        date.fromisoformat(iso_date): mock_result
        for iso_date, mock_result in spot_price_data.items()
    }

    async def _spot_price_fetcher(session, requested_date) -> OMIEResults | None:
        return data_by_date.get(requested_date)

    return _spot_price_fetcher
