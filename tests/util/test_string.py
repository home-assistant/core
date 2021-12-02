"""Test Home Assistant string util methods."""
from homeassistant.util.string import slugify


def test_slugify():
    """Test slugify."""
    assert slugify("T-!@#$!#@$!$est") == "t_est"
    assert slugify("Test More") == "test_more"
    assert slugify("Test_(More)") == "test_more"
    assert slugify("Tèst_Mörê") == "test_more"
    assert slugify("B8:27:EB:00:00:00") == "b8_27_eb_00_00_00"
    assert slugify("test.com") == "test_com"
    assert slugify("greg_phone - exp_wayp1") == "greg_phone_exp_wayp1"
    assert (
        slugify("We are, we are, a... Test Calendar") == "we_are_we_are_a_test_calendar"
    )
    assert slugify("Tèst_äöüß_ÄÖÜ") == "test_aouss_aou"
    assert slugify("影師嗎") == "ying_shi_ma"
    assert slugify("けいふぉんと") == "keihuonto"
    assert slugify("$") == "unknown"
    assert slugify("Ⓐ") == "unknown"
    assert slugify("ⓑ") == "unknown"
    assert slugify("$$$") == "unknown"
    assert slugify("$something") == "something"
    assert slugify("") == ""
    assert slugify(None) == ""
