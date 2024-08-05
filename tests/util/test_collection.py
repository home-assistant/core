"""Test collection utils."""

from homeassistant.util.collection import chunked_or_all


def test_chunked_or_all() -> None:
    """Test chunked_or_all can iterate chunk sizes larger than the passed in collection."""
    all_items = []
    incoming = (1, 2, 3, 4)
    for chunk in chunked_or_all(incoming, 2):
        assert len(chunk) == 2
        all_items.extend(chunk)
    assert all_items == [1, 2, 3, 4]

    all_items = []
    incoming = (1, 2, 3, 4)
    for chunk in chunked_or_all(incoming, 5):
        assert len(chunk) == 4
        # Verify the chunk is the same object as the incoming
        # collection since we want to avoid copying the collection
        # if we don't need to
        assert chunk is incoming
        all_items.extend(chunk)
    assert all_items == [1, 2, 3, 4]
