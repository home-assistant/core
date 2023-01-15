from homeassistant.util.color import check_valid_gamut,GamutType,XYPoint


GAMUT = GamutType(
    XYPoint(0.704, 0.296),
    XYPoint(0.2151, 0.7106),
    XYPoint(0.138, 0.08),
)
GAMUT_INVALID_1 = GamutType(
    XYPoint(0.704, 0.296),
    XYPoint(-0.201, 0.7106),
    XYPoint(0.138, 0.08),
)
GAMUT_INVALID_2 = GamutType(
    XYPoint(0.704, 1.296),
    XYPoint(0.2151, 0.7106),
    XYPoint(0.138, 0.08),
)
GAMUT_INVALID_3 = GamutType(
    XYPoint(0.1, 0.1),
    XYPoint(0.3, 0.3),
    XYPoint(0.7, 0.7),
)
GAMUT_INVALID_9 = GamutType(
    XYPoint(0.2, 0.5),
    XYPoint(0.3, 0.5),
    XYPoint(0.3, 1.1),
)
def test_check_valid_gamut():
    assert check_valid_gamut(GAMUT)==True
    assert check_valid_gamut(GAMUT_INVALID_1)==False
    assert check_valid_gamut(GAMUT_INVALID_2)==False
    assert check_valid_gamut(GAMUT_INVALID_3)==False
    assert check_valid_gamut(GAMUT_INVALID_9)==False

print('''Name       Stmts   Miss  Cover   Missing
----------------------------------------
color.py     279    224    25%   201-205, 215, 225-258, 265, 274-312, 317-353, 363-364, 369, 379-380, 385, 392-393, 400, 407-413, 420-425, 431-435, 443-461, 469-489, 494, 499, 507, 520-533, 543-549, 559-560, 570-576, 590-591, 596-599, 604-608, 613-618, 623, 628, 636, 641-643, 653-664, 675-702, 707-714
----------------------------------------
TOTAL        279    224    25%''')