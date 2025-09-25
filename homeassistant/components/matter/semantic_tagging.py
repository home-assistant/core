# codespell:ignore all

"""Provide Semantic Tags Translation functions."""

from chip.clusters import Objects as clusters

COMMON_CLOSURE_NAMESPACE = {
    # Tag Namespace 0x01
    0: "Opening",
    1: "Closing",
    2: "Stop",
}

COMMON_COMPASS_DIRECTION_NAMESPACE = {
    # Tag Namespace 0x02
    0: "Northward",
    1: "North-Eastward",
    2: "Eastward",
    3: "South-Eastward",
    4: "Southward",
    5: "South-Westward",
    6: "Westward",
    7: "North-Westward",
}

COMMON_COMPASS_LOCATION_NAMESPACE = {
    # Tag Namespace 0x03
    0: "North",
    1: "North-East",
    2: "East",
    3: "South-East",
    4: "South",
    5: "South-West",
    6: "West",
    7: "North-West",
}

COMMON_DIRECTION_NAMESPACE = {
    # Tag Namespace 0x04
    0: "Upward",
    1: "Downward",
    2: "Leftward",
    3: "Rightward",
    4: "Forward",
    5: "Backward",
}

COMMON_LEVEL_NAMESPACE = {
    # Tag Namespace 0x05
    0: "Low",
    1: "Medium",
    2: "High",
}


COMMON_LOCATION_NAMESPACE = {
    # Tag Namespace 0x06
    0: "Indoor",
    1: "Outdoor",
    2: "Inside",
    3: "Outside",
}

COMMON_NUMBER_NAMESPACE = {
    # Tag Namespace 0x07
    0: "Zero",
    1: "One",
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
    11: "Eleven",
    12: "Twelve",
    13: "Thirteen",
    14: "Fourteen",
    15: "Fifteen",
    16: "Sixteen",
    17: "Seventeen",
    18: "Eighteen",
    19: "Nineteen",
    20: "Twenty",
    21: "Twenty One",
    22: "Twenty Two",
    23: "Twenty Three",
    24: "Twenty Four",
    25: "Twenty Five",
    26: "Twenty Six",
    27: "Twenty Seven",
    28: "Twenty Eight",
    29: "Twenty Nine",
    30: "Thirty",
}

COMMON_POSITION_NAMESPACE = {
    # Tag Namespace 0x08
    0: "Left",
    1: "Right",
    2: "Top",
    3: "Bottom",
    4: "Middle",
    5: "Row",  # For future work, this needs custom handling to add the Numeric Value from the label.
    6: "Column",  # For future work, this needs custom handling to add the Numeric Value from the label.
}

COMMON_LANDMARK_NAMESPACE = {
    # Tag Namespace 0x11
    0: "Air Conditioner",
    1: "Air Purifier",
    2: "Back Door",
    3: "Bar Stool",
    4: "Bath Mat",
    5: "Bathtub",
    6: "Bed",
    7: "Bookshelf",
    8: "Chair",
    9: "Christmas Tree",
    10: "Coat Rack",
    11: "Coffee Table",
    12: "Cooking Range",
    13: "Couch",
    14: "Countertop",
    15: "Cradle",
    16: "Crib",
    17: "Desk",
    18: "Dining Table",
    19: "Dishwasher",
    20: "Door",
    21: "Dresser",
    22: "Laundry Dryer",
    23: "Fan",
    24: "Fireplace",
    25: "Freezer",
    26: "Front Door",
    27: "High Chair",
    28: "Kitchen Island",
    29: "Lamp",
    30: "Litter Box",
    31: "Mirror",
    32: "Nightstand",
    33: "Oven",
    34: "Pet Bed",
    35: "Pet Bowl",
    36: "Pet Crate",
    37: "Refrigerator",
    38: "Scratching Post",
    39: "Shoe Rack",
    40: "Shower",
    41: "Side Door",
    42: "Sink",
    43: "Sofa",
    44: "Stove",
    45: "Table",
    46: "Toilet",
    47: "Trash Can",
    48: "Laundry Washer",
    49: "Window",
    50: "Wine Cooler",
}

COMMON_RELATIVE_POSITION_NAMESPACE = {
    # Tag Namespace 0x12
    0: "Under",
    1: "Next To",
    2: "Around",
    3: "On",
    4: "Above",
    5: "Front Of",
    6: "Behind",
}

ELECTRICAL_MEASUREMENT_NAMESPACE = {
    # Tag Namespace 0x0A
    0: "AC",
    1: "DC",
    2: "ACPhase1",
    3: "ACPhase2",
    4: "ACPhase3",
}


COMMON_AREA_NAMESPACE = {
    # Tag Namespace 0x10
    0: "Aisle",
    1: "Attic",
    2: "Back Door",
    3: "Back yard",
    4: "Balcony",
    5: "Ballroom",
    6: "Bathroom",
    7: "Bedroom",
    8: "Border",
    9: "Boxroom",
    10: "Breakfast Room",
    11: "Carport",
    12: "Cellar",
    13: "Cloakroom",
    14: "Closet",
    15: "Conservatory",
    16: "Corridor",
    17: "Craft Room",
    18: "Cupboard",
    19: "Deck",
    20: "Den",
    21: "Dining Room",
    22: "Drawings Room",
    23: "Dressing Room",
    24: "Driveway",
    25: "Elevator",
    26: "Ensuite",
    27: "Entrance",
    28: "Entryway",
    29: "Family Room",
    30: "Foyer",
    31: "Front Door",
    32: "Front Yard",
    33: "Game Room",
    34: "Garage",
    35: "Garage Door",
    36: "Garden",
    37: "Garden Door",
    38: "Guest Bathroom",
    39: "Guest Bedroom",
    40: "Guest Room",
    41: "Gym",
    42: "Hallway",
    43: "Hearth Room",
    44: "Kids Room",
    45: "Kids Bedroom",
    46: "Kitchen",
    47: "Laundry Room",
    48: "Lawn",
    49: "Library",
    50: "Living Room",
    51: "Lounge",
    52: "Media Room",
    53: "Mud Room",
    54: "Music Room",
    55: "Nursery",
    56: "Office",
    57: "Outdoor Kitchen",
    58: "Outside",
    59: "Pantry",
    60: "Parking Lot",
    61: "Parlor",
    62: "Patio",
    63: "Play Room",
    64: "Pool Room",
    65: "Porch",
    66: "Primary Bathroom",
    67: "Primary Bedroom",
    68: "Ramp",
    69: "Reception Room",
    70: "Recreation Room",
    71: "Roof",
    72: "Sauna",
    73: "Scullery",
    74: "Sewing Room",
    75: "Shed",
    76: "Side Door",
    77: "Side Yard",
    78: "Sitting Room",
    79: "Snug",
    80: "Spa",
    81: "Staircase",
    82: "Steam Room",
    83: "Storage Room",
    84: "Studio",
    85: "Study",
    86: "Sun Room",
    87: "Swimming Pool",
    88: "Terrace",
    89: "Toilet",
    90: "Utility Room",
    91: "Ward",
    92: "Workshop",
}

LAUNDRY_NAMESPACE = {
    # Tag Namespace 0x0E
    0: "Normal",
    1: "Light Dry",
    2: "Extra Dry",
    3: "No Dry",
}

POWER_SOURCE_NAMESPACE = {
    # Tag Namespace 0x0F
    0: "Unknown",
    1: "Grid",
    2: "Solar",
    3: "Battery",
    4: "EV",
}

REFRIGERATOR_NAMESPACE = {
    # Tag Namespace 0x41
    0: "Refrigerator",
    1: "Freezer",
}

REFRIGERATOR_NAMESPACE = {
    # Tag Namespace 0x41
    0: "Refrigerator",
    1: "Freezer",
}

ROOM_AIR_CONDITIONER_NAMESPACE = {
    # Tag Namespace 0x42
    0: "Refrigerator",
    1: "Freezer",
}

SWITCHES_NAMESPACE = {
    # Tag Namespace 0x43
    0: "On",
    1: "Off",
    2: "Toggle",
    3: "Up",
    4: "Down",
    5: "Next",
    6: "Previous",
    7: "Enter/OK/Select",
    8: "Custom",  # For future work, this needs custom handling to add the text from the label.
}

SEMANTIC_TAGS: dict[int, dict[int, str]] = {
    0x01: COMMON_CLOSURE_NAMESPACE,
    0x02: COMMON_COMPASS_DIRECTION_NAMESPACE,
    0x03: COMMON_COMPASS_LOCATION_NAMESPACE,
    0x04: COMMON_DIRECTION_NAMESPACE,
    0x05: COMMON_LEVEL_NAMESPACE,
    0x06: COMMON_LOCATION_NAMESPACE,
    0x07: COMMON_NUMBER_NAMESPACE,
    0x08: COMMON_POSITION_NAMESPACE,
    0x11: COMMON_LANDMARK_NAMESPACE,
    0x12: COMMON_RELATIVE_POSITION_NAMESPACE,
    0x0A: ELECTRICAL_MEASUREMENT_NAMESPACE,
    0x10: COMMON_AREA_NAMESPACE,
    0x0E: LAUNDRY_NAMESPACE,
    0x0F: POWER_SOURCE_NAMESPACE,
    0x41: REFRIGERATOR_NAMESPACE,
    0x42: ROOM_AIR_CONDITIONER_NAMESPACE,
    0x43: SWITCHES_NAMESPACE,
}


def convert_tag_to_text(
    tag: clusters.Descriptor.Structs.SemanticTagStruct,
) -> str | None:
    """Get the label for a given tag."""
    # Special cases of the "Custom" tag in namespace 0x43.
    if tag.namespaceID == 0x43 and tag.tag == 0x08:
        return str(tag.label)

    # General case for all other tags.
    namespace_dict: dict[int, str] = SEMANTIC_TAGS.get(tag.namespaceID, {})
    tag_text: str | None = namespace_dict.get(tag.tag, None)
    if tag_text and tag.label:
        return f"{tag_text} {tag.label}"
    return tag_text
