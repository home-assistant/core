"""Support for fetching Vulcan data."""


async def get_lessons(client, date_from=None, date_to=None):
    """Support for fetching Vulcan lessons."""
    changes = {}
    list_ans = []
    async for lesson in await client.data.get_changed_lessons(
        date_from=date_from, date_to=date_to
    ):
        temp_dict = {}
        _id = str(lesson.id)
        temp_dict["id"] = lesson.id
        temp_dict["number"] = lesson.time.position if lesson.time is not None else None
        temp_dict["lesson"] = (
            lesson.subject.name if lesson.subject is not None else None
        )
        temp_dict["room"] = lesson.room.code if lesson.room is not None else None
        temp_dict["changes"] = lesson.changes
        temp_dict["note"] = lesson.note
        temp_dict["reason"] = lesson.reason
        temp_dict["event"] = lesson.event
        temp_dict["group"] = lesson.group
        temp_dict["teacher"] = (
            lesson.teacher.display_name if lesson.teacher is not None else None
        )
        temp_dict["from_to"] = (
            lesson.time.displayed_time if lesson.time is not None else None
        )

        changes[str(_id)] = temp_dict

    async for lesson in await client.data.get_lessons(
        date_from=date_from, date_to=date_to
    ):
        temp_dict = {}
        temp_dict["id"] = lesson.id
        temp_dict["number"] = lesson.time.position
        temp_dict["time"] = lesson.time
        temp_dict["date"] = lesson.date.date
        temp_dict["lesson"] = (
            lesson.subject.name if lesson.subject is not None else None
        )
        if lesson.room is not None:
            temp_dict["room"] = lesson.room.code
        else:
            temp_dict["room"] = "-"
        temp_dict["visible"] = lesson.visible
        temp_dict["changes"] = lesson.changes
        temp_dict["group"] = lesson.group
        temp_dict["reason"] = None
        temp_dict["teacher"] = (
            lesson.teacher.display_name if lesson.teacher is not None else None
        )
        temp_dict["from_to"] = (
            lesson.time.displayed_time if lesson.time is not None else None
        )
        if temp_dict["changes"] is None:
            temp_dict["changes"] = ""
        elif temp_dict["changes"].type == 1:
            temp_dict["lesson"] = f"Lekcja odwołana ({temp_dict['lesson']})"
            temp_dict["changes_info"] = f"Lekcja odwołana ({temp_dict['lesson']})"
            if str(temp_dict["changes"].id) in changes:
                temp_dict["reason"] = changes[str(temp_dict["changes"].id)]["reason"]
        elif temp_dict["changes"].type == 2:
            temp_dict["lesson"] = f"{temp_dict['lesson']} (Zastępstwo)"
            temp_dict["teacher"] = changes[str(temp_dict["changes"].id)]["teacher"]
            if str(temp_dict["changes"].id) in changes:
                temp_dict["teacher"] = changes[str(temp_dict["changes"].id)]["teacher"]
                temp_dict["reason"] = changes[str(temp_dict["changes"].id)]["reason"]
        elif temp_dict["changes"].type == 4:
            temp_dict["lesson"] = f"Lekcja odwołana ({temp_dict['lesson']})"
            if str(temp_dict["changes"].id) in changes:
                temp_dict["reason"] = changes[str(temp_dict["changes"].id)]["reason"]
        if temp_dict["visible"]:
            list_ans.append(temp_dict)

    return list_ans


async def get_student_info(client, student_id):
    """Support for fetching Student info by student id."""
    student_info = {}
    for student in await client.get_students():
        if str(student.pupil.id) == str(student_id):
            student_info["first_name"] = student.pupil.first_name
            if student.pupil.second_name:
                student_info["second_name"] = student.pupil.second_name
            student_info["last_name"] = student.pupil.last_name
            student_info["full_name"] = (
                f"{student.pupil.first_name} {student.pupil.last_name}"
            )
            student_info["id"] = student.pupil.id
            student_info["class"] = student.class_
            student_info["school"] = student.school.name
            student_info["symbol"] = student.symbol
            break
    return student_info
