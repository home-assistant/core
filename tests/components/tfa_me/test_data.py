"""Tests for the TFA.me integration: test of data.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

import pytest

from homeassistant.components.tfa_me.data import TFAmeData, TFAmeException


@pytest.mark.asyncio
async def test_tfame_data_init_and_host() -> None:
    """Test that TFAmeData initializes correctly with a host."""
    host = "192.168.1.100"
    client = TFAmeData(host)

    # host should be stored
    assert client.host == host


@pytest.mark.asyncio
async def test_tfame_data_get_identifier() -> None:
    """Test that get_identifier() returns the host."""
    host = "tfa-me-123-456-789"
    client = TFAmeData(host)

    identifier = await client.get_identifier()
    assert identifier == host


def test_tfame_data_raises_on_empty_host() -> None:
    """Test that empty host raises exception."""
    with pytest.raises(TFAmeException) as excinfo:
        TFAmeData("")  # Host/IP empty

    assert str(excinfo.value) == "host_empty"
