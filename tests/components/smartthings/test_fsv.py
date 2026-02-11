"""Test for SmartThings FSV (Field Service Value) settings."""

from homeassistant.components.smartthings.number import FSV_NUMBER_DESCRIPTIONS
from homeassistant.components.smartthings.select import FSV_SELECT_DESCRIPTIONS
from homeassistant.components.smartthings.switch import FSV_SWITCH_DESCRIPTIONS


def test_no_duplicate_fsv_ids() -> None:
    """Test that FSV IDs are not duplicated across select, number, and switch entities."""
    select_fsv_ids = set(FSV_SELECT_DESCRIPTIONS.keys())
    number_fsv_ids = set(FSV_NUMBER_DESCRIPTIONS.keys())
    switch_fsv_ids = set(FSV_SWITCH_DESCRIPTIONS.keys())

    # Check for duplicates between select and number
    select_number_duplicates = select_fsv_ids & number_fsv_ids
    assert not select_number_duplicates, (
        f"Found duplicate FSV IDs in both select and number: {sorted(select_number_duplicates)}. "
        "Each FSV ID should only be defined in one entity type."
    )

    # Check for duplicates between select and switch
    select_switch_duplicates = select_fsv_ids & switch_fsv_ids
    assert not select_switch_duplicates, (
        f"Found duplicate FSV IDs in both select and switch: {sorted(select_switch_duplicates)}. "
        "Each FSV ID should only be defined in one entity type."
    )

    # Check for duplicates between number and switch
    number_switch_duplicates = number_fsv_ids & switch_fsv_ids
    assert not number_switch_duplicates, (
        f"Found duplicate FSV IDs in both number and switch: {sorted(number_switch_duplicates)}. "
        "Each FSV ID should only be defined in one entity type."
    )
