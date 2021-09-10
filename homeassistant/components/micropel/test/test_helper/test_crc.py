"""Tests of CRC."""
from ...helper.crc import CRC


def test_get_crc():
    """Test if CRC SUM works."""
    expected_crc = "55"
    crc = CRC.get_crc_sum("*160220")
    assert expected_crc == crc

    expected_crc = "F9"
    crc = CRC.get_crc_sum("*16022012345678")
    assert expected_crc == crc

    expected_crc = "61"
    crc = CRC.get_crc_sum("@03*441802*441806")
    assert expected_crc == crc

    expected_crc = "05"
    crc = CRC.get_crc_sum("@03*4418021234*4418065678")
    assert expected_crc == crc

    expected_crc = "5E"
    crc = CRC.get_crc_sum("*0361646D696E64617400")
    assert expected_crc == crc

    expected_crc = "8D"
    crc = CRC.get_crc_sum("*03")
    assert expected_crc == crc

    expected_crc = "B4"
    crc = CRC.get_crc_sum("!16022035")
    assert expected_crc == crc
