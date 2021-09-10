"""EPNP protocol."""
from enum import Enum


class PropertyCategory(Enum):
    """Property categories."""

    INPUT_DIGITAL = 0
    INPUT_ANALOG = 1
    OUTPUT_DIGITAL = 2
    OUTPUT_ANALOG = 3
    USER_BIT = 4
    USER_REGISTER = 5
    FUNCTIONAL_BIT = 6
    FUNCTIONAL_REGISTER = 7


class PropertyType(Enum):
    """Property types."""

    BIT = 0
    WORD = 1
    LONG_WORD = 2


class SimpleProperty:
    """Simple property."""

    category: PropertyCategory
    type: PropertyType
    absolute_address: int
    ram_address: int
    mask: int
    net_property: bool
    net_index: int

    def __init__(
        self,
        category: PropertyCategory,
        type: PropertyType,
        absolute_address: int,
        ram_address: int,
        mask: int,
        net_property: bool,
        net_index: int,
    ):
        """Create simple property."""
        self.category = category
        self.type = type
        self.absolute_address = absolute_address
        self.ram_address = ram_address
        self.mask = mask
        self.net_property = net_property
        self.net_index = net_index


X0 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 0, 0x200, 1, False, -1
)
X1 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 1, 0x200, 2, False, -1
)
X2 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 2, 0x200, 4, False, -1
)
X3 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 3, 0x200, 8, False, -1
)
X4 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 4, 0x200, 16, False, -1
)
X5 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 5, 0x200, 32, False, -1
)
X6 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 6, 0x200, 64, False, -1
)
X7 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 7, 0x200, 128, False, -1
)
X8 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 8, 0x201, 1, False, -1
)
X9 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 9, 0x201, 2, False, -1
)
X10 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 10, 0x201, 4, False, -1
)
X11 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 11, 0x201, 8, False, -1
)
X12 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 12, 0x201, 16, False, -1
)
X13 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 13, 0x201, 32, False, -1
)
X14 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 14, 0x201, 64, False, -1
)
X15 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 15, 0x201, 128, False, -1
)
X16 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 16, 0x202, 1, False, -1
)
X17 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 17, 0x202, 2, False, -1
)
X18 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 18, 0x202, 4, False, -1
)
X19 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 19, 0x202, 8, False, -1
)
X20 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 20, 0x202, 16, False, -1
)
X21 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 21, 0x202, 32, False, -1
)
X22 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 22, 0x202, 64, False, -1
)
X23 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 23, 0x202, 128, False, -1
)
X24 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 24, 0x203, 1, False, -1
)
X25 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 25, 0x203, 2, False, -1
)
X26 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 26, 0x203, 4, False, -1
)
X27 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 27, 0x203, 8, False, -1
)
X28 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 28, 0x203, 16, False, -1
)
X29 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 29, 0x203, 32, False, -1
)
X30 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 30, 0x203, 64, False, -1
)
X31 = SimpleProperty(
    PropertyCategory.INPUT_DIGITAL, PropertyType.BIT, 31, 0x203, 128, False, -1
)
Y0 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 32, 0x204, 1, False, -1
)
Y1 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 33, 0x204, 2, False, -1
)
Y2 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 34, 0x204, 4, False, -1
)
Y3 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 35, 0x204, 8, False, -1
)
Y4 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 36, 0x204, 16, False, -1
)
Y5 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 37, 0x204, 32, False, -1
)
Y6 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 38, 0x204, 64, False, -1
)
Y7 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 39, 0x204, 128, False, -1
)
Y8 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 40, 0x205, 1, False, -1
)
Y9 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 41, 0x205, 2, False, -1
)
Y10 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 42, 0x205, 4, False, -1
)
Y11 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 43, 0x205, 8, False, -1
)
Y12 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 44, 0x205, 16, False, -1
)
Y13 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 45, 0x205, 32, False, -1
)
Y14 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 46, 0x205, 64, False, -1
)
Y15 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 47, 0x205, 128, False, -1
)
Y16 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 48, 0x206, 1, False, -1
)
Y17 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 49, 0x206, 2, False, -1
)
Y18 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 50, 0x206, 4, False, -1
)
Y19 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 51, 0x206, 8, False, -1
)
Y20 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 52, 0x206, 16, False, -1
)
Y21 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 53, 0x206, 32, False, -1
)
Y22 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 54, 0x206, 64, False, -1
)
Y23 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 55, 0x206, 128, False, -1
)
Y24 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 56, 0x207, 1, False, -1
)
Y25 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 57, 0x207, 2, False, -1
)
Y26 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 58, 0x207, 4, False, -1
)
Y27 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 59, 0x207, 8, False, -1
)
Y28 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 60, 0x207, 16, False, -1
)
Y29 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 61, 0x207, 32, False, -1
)
Y30 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 62, 0x207, 64, False, -1
)
Y31 = SimpleProperty(
    PropertyCategory.OUTPUT_DIGITAL, PropertyType.BIT, 63, 0x207, 128, False, -1
)
M0 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 64, 0x208, 1, False, -1
)
M1 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 65, 0x208, 2, False, -1
)
M2 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 66, 0x208, 4, False, -1
)
M3 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 67, 0x208, 8, False, -1
)
M4 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 68, 0x208, 16, False, -1
)
M5 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 69, 0x208, 32, False, -1
)
M6 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 70, 0x208, 64, False, -1
)
M7 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 71, 0x208, 128, False, -1
)
M8 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 72, 0x209, 1, False, -1
)
M9 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 73, 0x209, 2, False, -1
)
M10 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 74, 0x209, 4, False, -1
)
M11 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 75, 0x209, 8, False, -1
)
M12 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 76, 0x209, 16, False, -1
)
M13 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 77, 0x209, 32, False, -1
)
M14 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 78, 0x209, 64, False, -1
)
M15 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 79, 0x209, 128, False, -1
)
M16 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 80, 0x20A, 1, False, -1
)
M17 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 81, 0x20A, 2, False, -1
)
M18 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 82, 0x20A, 4, False, -1
)
M19 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 83, 0x20A, 8, False, -1
)
M20 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 84, 0x20A, 16, False, -1
)
M21 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 85, 0x20A, 32, False, -1
)
M22 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 86, 0x20A, 64, False, -1
)
M23 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 87, 0x20A, 128, False, -1
)
M24 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 88, 0x20B, 1, False, -1
)
M25 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 89, 0x20B, 2, False, -1
)
M26 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 90, 0x20B, 4, False, -1
)
M27 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 91, 0x20B, 8, False, -1
)
M28 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 92, 0x20B, 16, False, -1
)
M29 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 93, 0x20B, 32, False, -1
)
M30 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 94, 0x20B, 64, False, -1
)
M31 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 95, 0x20B, 128, False, -1
)
M32 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 96, 0x20C, 1, False, -1
)
M33 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 97, 0x20C, 2, False, -1
)
M34 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 98, 0x20C, 4, False, -1
)
M35 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 99, 0x20C, 8, False, -1
)
M36 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 100, 0x20C, 16, False, -1
)
M37 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 101, 0x20C, 32, False, -1
)
M38 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 102, 0x20C, 64, False, -1
)
M39 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 103, 0x20C, 128, False, -1
)
M40 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 104, 0x20D, 1, False, -1
)
M41 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 105, 0x20D, 2, False, -1
)
M42 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 106, 0x20D, 4, False, -1
)
M43 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 107, 0x20D, 8, False, -1
)
M44 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 108, 0x20D, 16, False, -1
)
M45 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 109, 0x20D, 32, False, -1
)
M46 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 110, 0x20D, 64, False, -1
)
M47 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 111, 0x20D, 128, False, -1
)
M48 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 112, 0x20E, 1, False, -1
)
M49 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 113, 0x20E, 2, False, -1
)
M50 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 114, 0x20E, 4, False, -1
)
M51 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 115, 0x20E, 8, False, -1
)
M52 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 116, 0x20E, 16, False, -1
)
M53 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 117, 0x20E, 32, False, -1
)
M54 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 118, 0x20E, 64, False, -1
)
M55 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 119, 0x20E, 128, False, -1
)
M56 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 120, 0x20F, 1, False, -1
)
M57 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 121, 0x20F, 2, False, -1
)
M58 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 122, 0x20F, 4, False, -1
)
M59 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 123, 0x20F, 8, False, -1
)
M60 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 124, 0x20F, 16, False, -1
)
M61 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 125, 0x20F, 32, False, -1
)
M62 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 126, 0x20F, 64, False, -1
)
M63 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 127, 0x20F, 128, False, -1
)
M64 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 128, 0x210, 1, True, 64
)
M65 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 129, 0x210, 2, True, 65
)
M66 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 130, 0x210, 4, True, 66
)
M67 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 131, 0x210, 8, True, 67
)
M68 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 132, 0x210, 16, True, 68
)
M69 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 133, 0x210, 32, True, 69
)
M70 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 134, 0x210, 64, True, 70
)
M71 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 135, 0x210, 128, True, 71
)
M72 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 136, 0x211, 1, True, 72
)
M73 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 137, 0x211, 2, True, 73
)
M74 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 138, 0x211, 4, True, 74
)
M75 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 139, 0x211, 8, True, 75
)
M76 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 140, 0x211, 16, True, 76
)
M77 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 141, 0x211, 32, True, 77
)
M78 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 142, 0x211, 64, True, 78
)
M79 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 143, 0x211, 128, True, 79
)
M80 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 144, 0x212, 1, True, 80
)
M81 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 145, 0x212, 2, True, 81
)
M82 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 146, 0x212, 4, True, 82
)
M83 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 147, 0x212, 8, True, 83
)
M84 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 148, 0x212, 16, True, 84
)
M85 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 149, 0x212, 32, True, 85
)
M86 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 150, 0x212, 64, True, 86
)
M87 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 151, 0x212, 128, True, 87
)
M88 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 152, 0x213, 1, True, 88
)
M89 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 153, 0x213, 2, True, 89
)
M90 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 154, 0x213, 4, True, 90
)
M91 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 155, 0x213, 8, True, 91
)
M92 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 156, 0x213, 16, True, 92
)
M93 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 157, 0x213, 32, True, 93
)
M94 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 158, 0x213, 64, True, 94
)
M95 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 159, 0x213, 128, True, 95
)
M96 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 160, 0x214, 1, True, 96
)
M97 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 161, 0x214, 2, True, 97
)
M98 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 162, 0x214, 4, True, 98
)
M99 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 163, 0x214, 8, True, 99
)
M100 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 164, 0x214, 16, True, 100
)
M101 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 165, 0x214, 32, True, 101
)
M102 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 166, 0x214, 64, True, 102
)
M103 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 167, 0x214, 128, True, 103
)
M104 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 168, 0x215, 1, True, 104
)
M105 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 169, 0x215, 2, True, 105
)
M106 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 170, 0x215, 4, True, 106
)
M107 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 171, 0x215, 8, True, 107
)
M108 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 172, 0x215, 16, True, 108
)
M109 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 173, 0x215, 32, True, 109
)
M110 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 174, 0x215, 64, True, 110
)
M111 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 175, 0x215, 128, True, 111
)
M112 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 176, 0x216, 1, True, 112
)
M113 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 177, 0x216, 2, True, 113
)
M114 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 178, 0x216, 4, True, 114
)
M115 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 179, 0x216, 8, True, 115
)
M116 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 180, 0x216, 16, True, 116
)
M117 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 181, 0x216, 32, True, 117
)
M118 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 182, 0x216, 64, True, 118
)
M119 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 183, 0x216, 128, True, 119
)
M120 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 184, 0x217, 1, True, 120
)
M121 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 185, 0x217, 2, True, 121
)
M122 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 186, 0x217, 4, True, 122
)
M123 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 187, 0x217, 8, True, 123
)
M124 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 188, 0x217, 16, True, 124
)
M125 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 189, 0x217, 32, True, 125
)
M126 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 190, 0x217, 64, True, 126
)
M127 = SimpleProperty(
    PropertyCategory.USER_BIT, PropertyType.BIT, 191, 0x217, 128, True, 127
)
B0 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 192, 0x218, 1, False, -1
)
B1 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 193, 0x218, 2, False, -1
)
B2 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 194, 0x218, 4, False, -1
)
B3 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 195, 0x218, 8, False, -1
)
B4 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 196, 0x218, 16, False, -1
)
B5 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 197, 0x218, 32, False, -1
)
B6 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 198, 0x218, 64, False, -1
)
B7 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 199, 0x218, 128, False, -1
)
B8 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 200, 0x219, 1, False, -1
)
B9 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 201, 0x219, 2, False, -1
)
B10 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 202, 0x219, 4, False, -1
)
B11 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 203, 0x219, 8, False, -1
)
B12 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 204, 0x219, 16, False, -1
)
B13 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 205, 0x219, 32, False, -1
)
B14 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 206, 0x219, 64, False, -1
)
B15 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 207, 0x219, 128, False, -1
)
B16 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 208, 0x21A, 1, False, -1
)
B17 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 209, 0x21A, 2, False, -1
)
B18 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 210, 0x21A, 4, False, -1
)
B19 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 211, 0x21A, 8, False, -1
)
B20 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 212, 0x21A, 16, False, -1
)
B21 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 213, 0x21A, 32, False, -1
)
B22 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 214, 0x21A, 64, False, -1
)
B23 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 215, 0x21A, 128, False, -1
)
B24 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 216, 0x21B, 1, False, -1
)
B25 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 217, 0x21B, 2, False, -1
)
B26 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 218, 0x21B, 4, False, -1
)
B27 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 219, 0x21B, 8, False, -1
)
B28 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 220, 0x21B, 16, False, -1
)
B29 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 221, 0x21B, 32, False, -1
)
B30 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 222, 0x21B, 64, False, -1
)
B31 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 223, 0x21B, 128, False, -1
)
B32 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 224, 0x21C, 1, False, -1
)
B33 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 225, 0x21C, 2, False, -1
)
B34 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 226, 0x21C, 4, False, -1
)
B35 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 227, 0x21C, 8, False, -1
)
B36 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 228, 0x21C, 16, False, -1
)
B37 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 229, 0x21C, 32, False, -1
)
B38 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 230, 0x21C, 64, False, -1
)
B39 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 231, 0x21C, 128, False, -1
)
B40 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 232, 0x21D, 1, False, -1
)
B41 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 233, 0x21D, 2, False, -1
)
B42 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 234, 0x21D, 4, False, -1
)
B43 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 235, 0x21D, 8, False, -1
)
B44 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 236, 0x21D, 16, False, -1
)
B45 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 237, 0x21D, 32, False, -1
)
B46 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 238, 0x21D, 64, False, -1
)
B47 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 239, 0x21D, 128, False, -1
)
B48 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 240, 0x21E, 1, False, -1
)
B49 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 241, 0x21E, 2, False, -1
)
B50 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 242, 0x21E, 4, False, -1
)
B51 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 243, 0x21E, 8, False, -1
)
B52 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 244, 0x21E, 16, False, -1
)
B53 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 245, 0x21E, 32, False, -1
)
B54 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 246, 0x21E, 64, False, -1
)
B55 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 247, 0x21E, 128, False, -1
)
B56 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 248, 0x21F, 1, False, -1
)
B57 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 249, 0x21F, 2, False, -1
)
B58 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 250, 0x21F, 4, False, -1
)
B59 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 251, 0x21F, 8, False, -1
)
B60 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 252, 0x21F, 16, False, -1
)
B61 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 253, 0x21F, 32, False, -1
)
B62 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 254, 0x21F, 64, False, -1
)
B63 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 255, 0x21F, 128, False, -1
)
B64 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 256, 0x220, 1, False, -1
)
B65 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 257, 0x220, 2, False, -1
)
B66 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 258, 0x220, 4, False, -1
)
B67 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 259, 0x220, 8, False, -1
)
B68 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 260, 0x220, 16, False, -1
)
B69 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 261, 0x220, 32, False, -1
)
B70 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 262, 0x220, 64, False, -1
)
B71 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 263, 0x220, 128, False, -1
)
B72 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 264, 0x221, 1, False, -1
)
B73 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 265, 0x221, 2, False, -1
)
B74 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 266, 0x221, 4, False, -1
)
B75 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 267, 0x221, 8, False, -1
)
B76 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 268, 0x221, 16, False, -1
)
B77 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 269, 0x221, 32, False, -1
)
B78 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 270, 0x221, 64, False, -1
)
B79 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 271, 0x221, 128, False, -1
)
B80 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 272, 0x222, 1, False, -1
)
B81 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 273, 0x222, 2, False, -1
)
B82 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 274, 0x222, 4, False, -1
)
B83 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 275, 0x222, 8, False, -1
)
B84 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 276, 0x222, 16, False, -1
)
B85 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 277, 0x222, 32, False, -1
)
B86 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 278, 0x222, 64, False, -1
)
B87 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 279, 0x222, 128, False, -1
)
B88 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 280, 0x223, 1, False, -1
)
B89 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 281, 0x223, 2, False, -1
)
B90 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 282, 0x223, 4, False, -1
)
B91 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 283, 0x223, 8, False, -1
)
B92 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 284, 0x223, 16, False, -1
)
B93 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 285, 0x223, 32, False, -1
)
B94 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 286, 0x223, 64, False, -1
)
B95 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 287, 0x223, 128, False, -1
)
B96 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 288, 0x224, 1, False, -1
)
B97 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 289, 0x224, 2, False, -1
)
B98 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 290, 0x224, 4, False, -1
)
B99 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 291, 0x224, 8, False, -1
)
B100 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 292, 0x224, 16, False, -1
)
B101 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 293, 0x224, 32, False, -1
)
B102 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 294, 0x224, 64, False, -1
)
B103 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 295, 0x224, 128, False, -1
)
B104 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 296, 0x225, 1, False, -1
)
B105 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 297, 0x225, 2, False, -1
)
B106 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 298, 0x225, 4, False, -1
)
B107 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 299, 0x225, 8, False, -1
)
B108 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 300, 0x225, 16, False, -1
)
B109 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 301, 0x225, 32, False, -1
)
B110 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 302, 0x225, 64, False, -1
)
B111 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 303, 0x225, 128, False, -1
)
B112 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 304, 0x226, 1, False, -1
)
B113 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 305, 0x226, 2, False, -1
)
B114 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 306, 0x226, 4, False, -1
)
B115 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 307, 0x226, 8, False, -1
)
B116 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 308, 0x226, 16, False, -1
)
B117 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 309, 0x226, 32, False, -1
)
B118 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 310, 0x226, 64, False, -1
)
B119 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 311, 0x226, 128, False, -1
)
B120 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 312, 0x227, 1, False, -1
)
B121 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 313, 0x227, 2, False, -1
)
B122 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 314, 0x227, 4, False, -1
)
B123 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 315, 0x227, 8, False, -1
)
B124 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 316, 0x227, 16, False, -1
)
B125 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 317, 0x227, 32, False, -1
)
B126 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 318, 0x227, 64, False, -1
)
B127 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_BIT, PropertyType.BIT, 319, 0x227, 128, False, -1
)
I0 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 0, 0x0, -1, False, -1
)
I1 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 1, 0x2, -1, False, -1
)
I2 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 2, 0x4, -1, False, -1
)
I3 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 3, 0x6, -1, False, -1
)
I4 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 4, 0x8, -1, False, -1
)
I5 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 5, 0xA, -1, False, -1
)
I6 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 6, 0xC, -1, False, -1
)
I7 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 7, 0xE, -1, False, -1
)
I8 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 8, 0x10, -1, False, -1
)
I9 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 9, 0x12, -1, False, -1
)
I10 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 10, 0x14, -1, False, -1
)
I11 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 11, 0x16, -1, False, -1
)
I12 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 12, 0x18, -1, False, -1
)
I13 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 13, 0x1A, -1, False, -1
)
I14 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 14, 0x1C, -1, False, -1
)
I15 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 15, 0x1E, -1, False, -1
)
I16 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 16, 0x20, -1, False, -1
)
I17 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 17, 0x22, -1, False, -1
)
I18 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 18, 0x24, -1, False, -1
)
I19 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 19, 0x26, -1, False, -1
)
I20 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 20, 0x28, -1, False, -1
)
I21 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 21, 0x2A, -1, False, -1
)
I22 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 22, 0x2C, -1, False, -1
)
I23 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 23, 0x2E, -1, False, -1
)
I24 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 24, 0x30, -1, False, -1
)
I25 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 25, 0x32, -1, False, -1
)
I26 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 26, 0x34, -1, False, -1
)
I27 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 27, 0x36, -1, False, -1
)
I28 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 28, 0x38, -1, False, -1
)
I29 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 29, 0x3A, -1, False, -1
)
I30 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 30, 0x3C, -1, False, -1
)
I31 = SimpleProperty(
    PropertyCategory.INPUT_ANALOG, PropertyType.WORD, 31, 0x3E, -1, False, -1
)
O0 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 32, 0x40, -1, False, -1
)
O1 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 33, 0x42, -1, False, -1
)
O2 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 34, 0x44, -1, False, -1
)
O3 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 35, 0x46, -1, False, -1
)
O4 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 36, 0x48, -1, False, -1
)
O5 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 37, 0x4A, -1, False, -1
)
O6 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 38, 0x4C, -1, False, -1
)
O7 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 39, 0x4E, -1, False, -1
)
O8 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 40, 0x50, -1, False, -1
)
O9 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 41, 0x52, -1, False, -1
)
O10 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 42, 0x54, -1, False, -1
)
O11 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 43, 0x56, -1, False, -1
)
O12 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 44, 0x58, -1, False, -1
)
O13 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 45, 0x5A, -1, False, -1
)
O14 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 46, 0x5C, -1, False, -1
)
O15 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 47, 0x5E, -1, False, -1
)
O16 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 48, 0x60, -1, False, -1
)
O17 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 49, 0x62, -1, False, -1
)
O18 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 50, 0x64, -1, False, -1
)
O19 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 51, 0x66, -1, False, -1
)
O20 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 52, 0x68, -1, False, -1
)
O21 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 53, 0x6A, -1, False, -1
)
O22 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 54, 0x6C, -1, False, -1
)
O23 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 55, 0x6E, -1, False, -1
)
O24 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 56, 0x70, -1, False, -1
)
O25 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 57, 0x72, -1, False, -1
)
O26 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 58, 0x74, -1, False, -1
)
O27 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 59, 0x76, -1, False, -1
)
O28 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 60, 0x78, -1, False, -1
)
O29 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 61, 0x7A, -1, False, -1
)
O30 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 62, 0x7C, -1, False, -1
)
O31 = SimpleProperty(
    PropertyCategory.OUTPUT_ANALOG, PropertyType.WORD, 63, 0x7E, -1, False, -1
)
D0 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 64, 0x80, -1, False, -1
)
D1 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 65, 0x82, -1, False, -1
)
D2 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 66, 0x84, -1, False, -1
)
D3 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 67, 0x86, -1, False, -1
)
D4 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 68, 0x88, -1, False, -1
)
D5 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 69, 0x8A, -1, False, -1
)
D6 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 70, 0x8C, -1, False, -1
)
D7 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 71, 0x8E, -1, False, -1
)
D8 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 72, 0x90, -1, False, -1
)
D9 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 73, 0x92, -1, False, -1
)
D10 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 74, 0x94, -1, False, -1
)
D11 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 75, 0x96, -1, False, -1
)
D12 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 76, 0x98, -1, False, -1
)
D13 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 77, 0x9A, -1, False, -1
)
D14 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 78, 0x9C, -1, False, -1
)
D15 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 79, 0x9E, -1, False, -1
)
D16 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 80, 0xA0, -1, False, -1
)
D17 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 81, 0xA2, -1, False, -1
)
D18 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 82, 0xA4, -1, False, -1
)
D19 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 83, 0xA6, -1, False, -1
)
D20 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 84, 0xA8, -1, False, -1
)
D21 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 85, 0xAA, -1, False, -1
)
D22 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 86, 0xAC, -1, False, -1
)
D23 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 87, 0xAE, -1, False, -1
)
D24 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 88, 0xB0, -1, False, -1
)
D25 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 89, 0xB2, -1, False, -1
)
D26 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 90, 0xB4, -1, False, -1
)
D27 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 91, 0xB6, -1, False, -1
)
D28 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 92, 0xB8, -1, False, -1
)
D29 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 93, 0xBA, -1, False, -1
)
D30 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 94, 0xBC, -1, False, -1
)
D31 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 95, 0xBE, -1, False, -1
)
D32 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 96, 0xC0, -1, True, 32
)
D33 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 97, 0xC2, -1, True, 33
)
D34 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 98, 0xC4, -1, True, 34
)
D35 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 99, 0xC6, -1, True, 35
)
D36 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 100, 0xC8, -1, True, 36
)
D37 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 101, 0xCA, -1, True, 37
)
D38 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 102, 0xCC, -1, True, 38
)
D39 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 103, 0xCE, -1, True, 39
)
D40 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 104, 0xD0, -1, True, 40
)
D41 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 105, 0xD2, -1, True, 41
)
D42 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 106, 0xD4, -1, True, 42
)
D43 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 107, 0xD6, -1, True, 43
)
D44 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 108, 0xD8, -1, True, 44
)
D45 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 109, 0xDA, -1, True, 45
)
D46 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 110, 0xDC, -1, True, 46
)
D47 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 111, 0xDE, -1, True, 47
)
D48 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 112, 0xE0, -1, True, 48
)
D49 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 113, 0xE2, -1, True, 49
)
D50 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 114, 0xE4, -1, True, 50
)
D51 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 115, 0xE6, -1, True, 51
)
D52 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 116, 0xE8, -1, True, 52
)
D53 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 117, 0xEA, -1, True, 53
)
D54 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 118, 0xEC, -1, True, 54
)
D55 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 119, 0xEE, -1, True, 55
)
D56 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 120, 0xF0, -1, True, 56
)
D57 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 121, 0xF2, -1, True, 57
)
D58 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 122, 0xF4, -1, True, 58
)
D59 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 123, 0xF6, -1, True, 59
)
D60 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 124, 0xF8, -1, True, 60
)
D61 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 125, 0xFA, -1, True, 61
)
D62 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 126, 0xFC, -1, True, 62
)
D63 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.WORD, 127, 0xFE, -1, True, 63
)
W0 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 128, 0x100, -1, False, -1
)
W1 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 129, 0x102, -1, False, -1
)
W2 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 130, 0x104, -1, False, -1
)
W3 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 131, 0x106, -1, False, -1
)
W4 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 132, 0x108, -1, False, -1
)
W5 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 133, 0x10A, -1, False, -1
)
W6 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 134, 0x10C, -1, False, -1
)
W7 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 135, 0x10E, -1, False, -1
)
W8 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 136, 0x110, -1, False, -1
)
W9 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 137, 0x112, -1, False, -1
)
W10 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 138, 0x114, -1, False, -1
)
W11 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 139, 0x116, -1, False, -1
)
W12 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 140, 0x118, -1, False, -1
)
W13 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 141, 0x11A, -1, False, -1
)
W14 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 142, 0x11C, -1, False, -1
)
W15 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 143, 0x11E, -1, False, -1
)
W16 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 144, 0x120, -1, False, -1
)
W17 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 145, 0x122, -1, False, -1
)
W18 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 146, 0x124, -1, False, -1
)
W19 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 147, 0x126, -1, False, -1
)
W20 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 148, 0x128, -1, False, -1
)
W21 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 149, 0x12A, -1, False, -1
)
W22 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 150, 0x12C, -1, False, -1
)
W23 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 151, 0x12E, -1, False, -1
)
W24 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 152, 0x130, -1, False, -1
)
W25 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 153, 0x132, -1, False, -1
)
W26 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 154, 0x134, -1, False, -1
)
W27 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 155, 0x136, -1, False, -1
)
W28 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 156, 0x138, -1, False, -1
)
W29 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 157, 0x13A, -1, False, -1
)
W30 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 158, 0x13C, -1, False, -1
)
W31 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 159, 0x13E, -1, False, -1
)
W32 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 160, 0x140, -1, False, -1
)
W33 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 161, 0x142, -1, False, -1
)
W34 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 162, 0x144, -1, False, -1
)
W35 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 163, 0x146, -1, False, -1
)
W36 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 164, 0x148, -1, False, -1
)
W37 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 165, 0x14A, -1, False, -1
)
W38 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 166, 0x14C, -1, False, -1
)
W39 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 167, 0x14E, -1, False, -1
)
W40 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 168, 0x150, -1, False, -1
)
W41 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 169, 0x152, -1, False, -1
)
W42 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 170, 0x154, -1, False, -1
)
W43 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 171, 0x156, -1, False, -1
)
W44 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 172, 0x158, -1, False, -1
)
W45 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 173, 0x15A, -1, False, -1
)
W46 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 174, 0x15C, -1, False, -1
)
W47 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 175, 0x15E, -1, False, -1
)
W48 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 176, 0x160, -1, False, -1
)
W49 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 177, 0x162, -1, False, -1
)
W50 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 178, 0x164, -1, False, -1
)
W51 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 179, 0x166, -1, False, -1
)
W52 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 180, 0x168, -1, False, -1
)
W53 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 181, 0x16A, -1, False, -1
)
W54 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 182, 0x16C, -1, False, -1
)
W55 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 183, 0x16E, -1, False, -1
)
W56 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 184, 0x170, -1, False, -1
)
W57 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 185, 0x172, -1, False, -1
)
W58 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 186, 0x174, -1, False, -1
)
W59 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 187, 0x176, -1, False, -1
)
W60 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 188, 0x178, -1, False, -1
)
W61 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 189, 0x17A, -1, False, -1
)
W62 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 190, 0x17C, -1, False, -1
)
W63 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 191, 0x17E, -1, False, -1
)
W64 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 192, 0x180, -1, False, -1
)
W65 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 193, 0x182, -1, False, -1
)
W66 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 194, 0x184, -1, False, -1
)
W67 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 195, 0x186, -1, False, -1
)
W68 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 196, 0x188, -1, False, -1
)
W69 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 197, 0x18A, -1, False, -1
)
W70 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 198, 0x18C, -1, False, -1
)
W71 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 199, 0x18E, -1, False, -1
)
W72 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 200, 0x190, -1, False, -1
)
W73 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 201, 0x192, -1, False, -1
)
W74 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 202, 0x194, -1, False, -1
)
W75 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 203, 0x196, -1, False, -1
)
W76 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 204, 0x198, -1, False, -1
)
W77 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 205, 0x19A, -1, False, -1
)
W78 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 206, 0x19C, -1, False, -1
)
W79 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 207, 0x19E, -1, False, -1
)
W80 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 208, 0x1A0, -1, False, -1
)
W81 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 209, 0x1A2, -1, False, -1
)
W82 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 210, 0x1A4, -1, False, -1
)
W83 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 211, 0x1A6, -1, False, -1
)
W84 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 212, 0x1A8, -1, False, -1
)
W85 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 213, 0x1AA, -1, False, -1
)
W86 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 214, 0x1AC, -1, False, -1
)
W87 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 215, 0x1AE, -1, False, -1
)
W88 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 216, 0x1B0, -1, False, -1
)
W89 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 217, 0x1B2, -1, False, -1
)
W90 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 218, 0x1B4, -1, False, -1
)
W91 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 219, 0x1B6, -1, False, -1
)
W92 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 220, 0x1B8, -1, False, -1
)
W93 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 221, 0x1BA, -1, False, -1
)
W94 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 222, 0x1BC, -1, False, -1
)
W95 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 223, 0x1BE, -1, False, -1
)
W96 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 224, 0x1C0, -1, False, -1
)
W97 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 225, 0x1C2, -1, False, -1
)
W98 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 226, 0x1C4, -1, False, -1
)
W99 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 227, 0x1C6, -1, False, -1
)
W100 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 228, 0x1C8, -1, False, -1
)
W101 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 229, 0x1CA, -1, False, -1
)
W102 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 230, 0x1CC, -1, False, -1
)
W103 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 231, 0x1CE, -1, False, -1
)
W104 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 232, 0x1D0, -1, False, -1
)
W105 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 233, 0x1D2, -1, False, -1
)
W106 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 234, 0x1D4, -1, False, -1
)
W107 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 235, 0x1D6, -1, False, -1
)
W108 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 236, 0x1D8, -1, False, -1
)
W109 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 237, 0x1DA, -1, False, -1
)
W110 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 238, 0x1DC, -1, False, -1
)
W111 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 239, 0x1DE, -1, False, -1
)
W112 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 240, 0x1E0, -1, False, -1
)
W113 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 241, 0x1E2, -1, False, -1
)
W114 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 242, 0x1E4, -1, False, -1
)
W115 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 243, 0x1E6, -1, False, -1
)
W116 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 244, 0x1E8, -1, False, -1
)
W117 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 245, 0x1EA, -1, False, -1
)
W118 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 246, 0x1EC, -1, False, -1
)
W119 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 247, 0x1EE, -1, False, -1
)
W120 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 248, 0x1F0, -1, False, -1
)
W121 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 249, 0x1F2, -1, False, -1
)
W122 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 250, 0x1F4, -1, False, -1
)
W123 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 251, 0x1F6, -1, False, -1
)
W124 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 252, 0x1F8, -1, False, -1
)
W125 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 253, 0x1FA, -1, False, -1
)
W126 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 254, 0x1FC, -1, False, -1
)
W127 = SimpleProperty(
    PropertyCategory.FUNCTIONAL_REGISTER, PropertyType.WORD, 255, 0x1FE, -1, False, -1
)
LW0 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, 0, 0x600, -1, True, 0
)
LW1 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x604, -1, True, 1
)
LW2 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x608, -1, True, 2
)
LW3 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x60C, -1, True, 3
)
LW4 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x610, -1, True, 4
)
LW5 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x614, -1, True, 5
)
LW6 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x618, -1, True, 6
)
LW7 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x61C, -1, True, 7
)
LW8 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x620, -1, True, 8
)
LW9 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x624, -1, True, 9
)
LW10 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x628, -1, True, 10
)
LW11 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x62C, -1, True, 11
)
LW12 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x630, -1, True, 12
)
LW13 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x634, -1, True, 13
)
LW14 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x638, -1, True, 14
)
LW15 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x63C, -1, True, 15
)
LW16 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x640, -1, True, 16
)
LW17 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x644, -1, True, 17
)
LW18 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x648, -1, True, 18
)
LW19 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x64C, -1, True, 19
)
LW20 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x650, -1, True, 20
)
LW21 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x654, -1, True, 21
)
LW22 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x658, -1, True, 22
)
LW23 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x65C, -1, True, 23
)
LW24 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x660, -1, True, 24
)
LW25 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x664, -1, True, 25
)
LW26 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x668, -1, True, 26
)
LW27 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x66C, -1, True, 27
)
LW28 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x670, -1, True, 28
)
LW29 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x674, -1, True, 29
)
LW30 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x678, -1, True, 30
)
LW31 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x67C, -1, True, 31
)
LW32 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x680, -1, True, 32
)
LW33 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x684, -1, True, 33
)
LW34 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x688, -1, True, 34
)
LW35 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x68C, -1, True, 35
)
LW36 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x690, -1, True, 36
)
LW37 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x694, -1, True, 37
)
LW38 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x698, -1, True, 38
)
LW39 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x69C, -1, True, 39
)
LW40 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6A0, -1, True, 40
)
LW41 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6A4, -1, True, 41
)
LW42 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6A8, -1, True, 42
)
LW43 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6AC, -1, True, 43
)
LW44 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6B0, -1, True, 44
)
LW45 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6B4, -1, True, 45
)
LW46 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6B8, -1, True, 46
)
LW47 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6BC, -1, True, 47
)
LW48 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6C0, -1, True, 48
)
LW49 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6C4, -1, True, 49
)
LW50 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6C8, -1, True, 50
)
LW51 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6CC, -1, True, 51
)
LW52 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6D0, -1, True, 52
)
LW53 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6D4, -1, True, 53
)
LW54 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6D8, -1, True, 54
)
LW55 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6DC, -1, True, 55
)
LW56 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6E0, -1, True, 56
)
LW57 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6E4, -1, True, 57
)
LW58 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6E8, -1, True, 58
)
LW59 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6EC, -1, True, 59
)
LW60 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6F0, -1, True, 60
)
LW61 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6F4, -1, True, 61
)
LW62 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6F8, -1, True, 62
)
LW63 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x6FC, -1, True, 63
)
LW64 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x700, -1, True, 64
)
LW65 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x704, -1, True, 65
)
LW66 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x708, -1, True, 66
)
LW67 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x70C, -1, True, 67
)
LW68 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x710, -1, True, 68
)
LW69 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x714, -1, True, 69
)
LW70 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x718, -1, True, 70
)
LW71 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x71C, -1, True, 71
)
LW72 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x720, -1, True, 72
)
LW73 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x724, -1, True, 73
)
LW74 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x728, -1, True, 74
)
LW75 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x72C, -1, True, 75
)
LW76 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x730, -1, True, 76
)
LW77 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x734, -1, True, 77
)
LW78 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x738, -1, True, 78
)
LW79 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x73C, -1, True, 79
)
LW80 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x740, -1, True, 80
)
LW81 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x744, -1, True, 81
)
LW82 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x748, -1, True, 82
)
LW83 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x74C, -1, True, 83
)
LW84 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x750, -1, True, 84
)
LW85 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x754, -1, True, 85
)
LW86 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x758, -1, True, 86
)
LW87 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x75C, -1, True, 87
)
LW88 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x760, -1, True, 88
)
LW89 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x764, -1, True, 89
)
LW90 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x768, -1, True, 90
)
LW91 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x76C, -1, True, 91
)
LW92 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x770, -1, True, 92
)
LW93 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x774, -1, True, 93
)
LW94 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x778, -1, True, 94
)
LW95 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x77C, -1, True, 95
)
LW96 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x780, -1, True, 96
)
LW97 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x784, -1, True, 97
)
LW98 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x788, -1, True, 98
)
LW99 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x78C, -1, True, 99
)
LW100 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x790, -1, True, 100
)
LW101 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x794, -1, True, 101
)
LW102 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x798, -1, True, 102
)
LW103 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x79C, -1, True, 103
)
LW104 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7A0, -1, True, 104
)
LW105 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7A4, -1, True, 105
)
LW106 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7A8, -1, True, 106
)
LW107 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7AC, -1, True, 107
)
LW108 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7B0, -1, True, 108
)
LW109 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7B4, -1, True, 109
)
LW110 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7B8, -1, True, 110
)
LW111 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7BC, -1, True, 111
)
LW112 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7C0, -1, True, 112
)
LW113 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7C4, -1, True, 113
)
LW114 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7C8, -1, True, 114
)
LW115 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7CC, -1, True, 115
)
LW116 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7D0, -1, True, 116
)
LW117 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7D4, -1, True, 117
)
LW118 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7D8, -1, True, 118
)
LW119 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7DC, -1, True, 119
)
LW120 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7E0, -1, True, 120
)
LW121 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7E4, -1, True, 121
)
LW122 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7E8, -1, True, 122
)
LW123 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7EC, -1, True, 123
)
LW124 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7F0, -1, True, 124
)
LW125 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7F4, -1, True, 125
)
LW126 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7F8, -1, True, 126
)
LW127 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x7FC, -1, True, 127
)
LW128 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x800, -1, True, 128
)
LW129 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x804, -1, True, 129
)
LW130 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x808, -1, True, 130
)
LW131 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x80C, -1, True, 131
)
LW132 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x810, -1, True, 132
)
LW133 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x814, -1, True, 133
)
LW134 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x818, -1, True, 134
)
LW135 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x81C, -1, True, 135
)
LW136 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x820, -1, True, 136
)
LW137 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x824, -1, True, 137
)
LW138 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x828, -1, True, 138
)
LW139 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x82C, -1, True, 139
)
LW140 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x830, -1, True, 140
)
LW141 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x834, -1, True, 141
)
LW142 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x838, -1, True, 142
)
LW143 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x83C, -1, True, 143
)
LW144 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x840, -1, True, 144
)
LW145 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x844, -1, True, 145
)
LW146 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x848, -1, True, 146
)
LW147 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x84C, -1, True, 147
)
LW148 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x850, -1, True, 148
)
LW149 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x854, -1, True, 149
)
LW150 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x858, -1, True, 150
)
LW151 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x85C, -1, True, 151
)
LW152 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x860, -1, True, 152
)
LW153 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x864, -1, True, 153
)
LW154 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x868, -1, True, 154
)
LW155 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x86C, -1, True, 155
)
LW156 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x870, -1, True, 156
)
LW157 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x874, -1, True, 157
)
LW158 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x878, -1, True, 158
)
LW159 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x87C, -1, True, 159
)
LW160 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x880, -1, True, 160
)
LW161 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x884, -1, True, 161
)
LW162 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x888, -1, True, 162
)
LW163 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x88C, -1, True, 163
)
LW164 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x890, -1, True, 164
)
LW165 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x894, -1, True, 165
)
LW166 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x898, -1, True, 166
)
LW167 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x89C, -1, True, 167
)
LW168 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8A0, -1, True, 168
)
LW169 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8A4, -1, True, 169
)
LW170 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8A8, -1, True, 170
)
LW171 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8AC, -1, True, 171
)
LW172 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8B0, -1, True, 172
)
LW173 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8B4, -1, True, 173
)
LW174 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8B8, -1, True, 174
)
LW175 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8BC, -1, True, 175
)
LW176 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8C0, -1, True, 176
)
LW177 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8C4, -1, True, 177
)
LW178 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8C8, -1, True, 178
)
LW179 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8CC, -1, True, 179
)
LW180 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8D0, -1, True, 180
)
LW181 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8D4, -1, True, 181
)
LW182 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8D8, -1, True, 182
)
LW183 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8DC, -1, True, 183
)
LW184 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8E0, -1, True, 184
)
LW185 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8E4, -1, True, 185
)
LW186 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8E8, -1, True, 186
)
LW187 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8EC, -1, True, 187
)
LW188 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8F0, -1, True, 188
)
LW189 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8F4, -1, True, 189
)
LW190 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8F8, -1, True, 190
)
LW191 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x8FC, -1, True, 191
)
LW192 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x900, -1, True, 192
)
LW193 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x904, -1, True, 193
)
LW194 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x908, -1, True, 194
)
LW195 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x90C, -1, True, 195
)
LW196 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x910, -1, True, 196
)
LW197 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x914, -1, True, 197
)
LW198 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x918, -1, True, 198
)
LW199 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x91C, -1, True, 199
)
LW200 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x920, -1, True, 200
)
LW201 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x924, -1, True, 201
)
LW202 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x928, -1, True, 202
)
LW203 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x92C, -1, True, 203
)
LW204 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x930, -1, True, 204
)
LW205 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x934, -1, True, 205
)
LW206 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x938, -1, True, 206
)
LW207 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x93C, -1, True, 207
)
LW208 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x940, -1, True, 208
)
LW209 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x944, -1, True, 209
)
LW210 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x948, -1, True, 210
)
LW211 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x94C, -1, True, 211
)
LW212 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x950, -1, True, 212
)
LW213 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x954, -1, True, 213
)
LW214 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x958, -1, True, 214
)
LW215 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x95C, -1, True, 215
)
LW216 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x960, -1, True, 216
)
LW217 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x964, -1, True, 217
)
LW218 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x968, -1, True, 218
)
LW219 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x96C, -1, True, 219
)
LW220 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x970, -1, True, 220
)
LW221 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x974, -1, True, 221
)
LW222 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x978, -1, True, 222
)
LW223 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x97C, -1, True, 223
)
LW224 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x980, -1, True, 224
)
LW225 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x984, -1, True, 225
)
LW226 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x988, -1, True, 226
)
LW227 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x98C, -1, True, 227
)
LW228 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x990, -1, True, 228
)
LW229 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x994, -1, True, 229
)
LW230 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x998, -1, True, 230
)
LW231 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x99C, -1, True, 231
)
LW232 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9A0, -1, True, 232
)
LW233 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9A4, -1, True, 233
)
LW234 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9A8, -1, True, 234
)
LW235 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9AC, -1, True, 235
)
LW236 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9B0, -1, True, 236
)
LW237 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9B4, -1, True, 237
)
LW238 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9B8, -1, True, 238
)
LW239 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9BC, -1, True, 239
)
LW240 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9C0, -1, True, 240
)
LW241 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9C4, -1, True, 241
)
LW242 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9C8, -1, True, 242
)
LW243 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9CC, -1, True, 243
)
LW244 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9D0, -1, True, 244
)
LW245 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9D4, -1, True, 245
)
LW246 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9D8, -1, True, 246
)
LW247 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9DC, -1, True, 247
)
LW248 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9E0, -1, True, 248
)
LW249 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9E4, -1, True, 249
)
LW250 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9E8, -1, True, 250
)
LW251 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9EC, -1, True, 251
)
LW252 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9F0, -1, True, 252
)
LW253 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9F4, -1, True, 253
)
LW254 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9F8, -1, True, 254
)
LW255 = SimpleProperty(
    PropertyCategory.USER_REGISTER, PropertyType.LONG_WORD, -1, 0x9FC, -1, True, 255
)
