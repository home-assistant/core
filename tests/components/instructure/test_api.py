"""Test the canvas config flow."""
# from unittest.mock import AsyncMock

# import pytest

# from homeassistant import config_entries
# from homeassistant.components.instructure.canvas_api import CanvasAPI
# from homeassistant.components.instructure.const import DOMAIN
# from homeassistant.components.instructure.coordinator import CanvasUpdateCoordinator
# from homeassistant.core import HomeAssistant

# TEST_ACCESS_TOKEN = "test_access_token"
# TEST_HOST_PREFIX = "chalmers"

# # Get one course
# # Get multiple courses
# # get one assignment which due date passed and assignment submitted
# # get one assignment which due date passed and assignment not submitted
# # Get one assignment which due date is not passed and assignment submitted
# # Get one assignment which due date is not passed and assignment not submitted
# # ....

# # - Bu fonksiyondan çıkan output benim course objesi ile aynı mı? => ASAGI YUKARI AYNI BAXI DEEGERLER SET EDILMEMIS
# # - Config flowu mocklamam lazım galiba burada. Onları hallet. Tek tek neleri mocklamam lazım karar ver
# # - Printleyerek debug yapacağız.
# # - Enrty ve hass'ı printleceğim.
# # {
# #         "entry_id": "20b0eff56f836452061aede3117f9ac8",
# #         "version": 1,
# #         "domain": "instructure",
# #         "title": "Canvas",
# #         "data": {
# #           "host_prefix": "chalmers",
# #           "access_token": "12523~XXIpQXiDpoNnq7S7fZv21Z3yTVyjLbsR31kzjKLXO7hDGKw1gRpIe2jywr8S67YW"
# #         },
# #         "options": {
# #           "courses": {
# #             "25271": "DAT265 / DIT588 Software evolution project"
# #           }
# #         },
# #         "pref_disable_new_entities": false,
# #         "pref_disable_polling": false,
# #         "source": "user",
# #         "unique_id": null,
# #         "disabled_by": null
# # }
# # async def test_async_get_courses(hass: HomeAssistant) -> None:
# #     """Test the get courses method."""

# #     entry = MockConfigEntry(domain=DOMAIN, data={
# #         "host_prefix": "chalmers",
# #         'access_token': 'mock_access_token'
# #     }, options={
# #         'courses':{"DAT265 / DIT588 Software evolution project"}})

# #     entry.add_to_hass(hass)
# #     with patch(
# #             "homeassistant.components.instructure.CanvasAPI.async_get_courses", return_value=COURSES,
# #         ):
# #         await hass.config_entries.async_setup(entry.entry_id)
# #         await hass.async_block_till_done()
# #         assert entry.state is config_entries.ConfigEntryState.LOADED
# #         assert DOMAIN in hass.data
# #         print(hass.data[DOMAIN][entry.entry_id])
# #         assert hass.data[DOMAIN][entry.entry_id]['coordinator'].selected_courses is COURSES['id']

# pytestmark = pytest.mark.usefixtures("mock_setup_entry")


# async def test_async_get_assignments(
#     hass: HomeAssistant, mock_setup_entry: AsyncMock
# ) -> None:
#     """Create a mock CanvasUpdateCoordinator object."""
#     print(hass)
#     print(hass.data)
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": config_entries.SOURCE_USER}
#     )

#     result = await hass.config_entries.flow.async_configure(
#         result["flow_id"],
#         user_input={
#             "host_prefix": TEST_HOST_PREFIX,
#             "access_token": TEST_ACCESS_TOKEN,
#         },
#     )

#     course_ids = ["course1", "course2"]
#     expected_assignments = {
#         "assignment-1": {"id": 1, "due_at": "2023-12-20T00:00:00Z"},
#         "assignment-2": {"id": 2, "due_at": "2023-12-21T00:00:00Z"},
#     }
#     mock_api = AsyncMock(spec=CanvasAPI)
#     mock_api.async_get_upcoming_assignments = AsyncMock(
#         return_value=expected_assignments
#     )
#     coordinator = CanvasUpdateCoordinator(hass=hass, entry=AsyncMock(), api=mock_api)
#     await coordinator.async_update_data()
#     assignments = await mock_api.async_get_upcoming_assignments(course_ids)

#     # Assert that the returned assignments match the expected assignments
#     assert assignments == expected_assignments
