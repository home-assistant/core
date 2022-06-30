"""Make sure that handling real world LG HomeKit characteristics isn't broken."""

from homeassistant.components.media_player.const import (
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_SELECT_SOURCE,
)

from tests.components.homekit_controller.common import (
    HUB_TEST_ACCESSORY_ID,
    DeviceTestInfo,
    EntityTestInfo,
    assert_devices_and_entities_created,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_lg_tv(hass):
    """Test that a Koogeek LS1 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, "lg_tv.json")
    await setup_test_accessories(hass, accessories)

    await assert_devices_and_entities_created(
        hass,
        DeviceTestInfo(
            unique_id=HUB_TEST_ACCESSORY_ID,
            name="LG webOS TV AF80",
            model="OLED55B9PUA",
            manufacturer="LG Electronics",
            sw_version="04.71.04",
            hw_version="1",
            serial_number="999AAAAAA999",
            devices=[],
            entities=[
                EntityTestInfo(
                    entity_id="media_player.lg_webos_tv_af80",
                    friendly_name="LG webOS TV AF80",
                    unique_id="homekit-999AAAAAA999-48",
                    supported_features=(
                        SUPPORT_PAUSE | SUPPORT_PLAY | SUPPORT_SELECT_SOURCE
                    ),
                    capabilities={
                        "source_list": [
                            "AirPlay",
                            "Live TV",
                            "HDMI 1",
                            "Sony",
                            "Apple",
                            "AV",
                            "HDMI 4",
                        ]
                    },
                    # The LG TV doesn't (at least at this patch level) report
                    # its media state via CURRENT_MEDIA_STATE. Therefore "ok"
                    # is the best we can say.
                    state="ok",
                ),
            ],
        ),
    )

    """
    assert state.attributes["source"] == "HDMI 4"
    """
