"""Support for fetching Vulcan data."""


async def get_lessons(client, date_from=None, date_to=None):
    """Support for fetching Vulcan lessons."""
    changes = {}
    list_ans = []
    async for Lesson in await client.data.get_changed_lessons(
        date_from=date_from, date_to=date_to
    ):
        temp_dict = {}
        id = str(Lesson.id)
        temp_dict["id"] = Lesson.id
        temp_dict["number"] = Lesson.time.position if Lesson.time is not None else None
        temp_dict["lesson"] = (
            Lesson.subject.name if Lesson.subject is not None else None
        )
        temp_dict["room"] = Lesson.room.code if Lesson.room is not None else None
        temp_dict["changes"] = Lesson.changes
        temp_dict["note"] = Lesson.note
        temp_dict["reason"] = Lesson.reason
        temp_dict["event"] = Lesson.event
        temp_dict["group"] = Lesson.group
        temp_dict["teacher"] = (
            Lesson.teacher.display_name if Lesson.teacher is not None else None
        )
        temp_dict["from_to"] = (
            Lesson.time.displayed_time if Lesson.time is not None else None
        )

        changes[str(id)] = temp_dict

    async for Lesson in await client.data.get_lessons(
        date_from=date_from, date_to=date_to
    ):
        temp_dict = {}
        temp_dict["id"] = Lesson.id
        temp_dict["number"] = Lesson.time.position
        temp_dict["time"] = Lesson.time
        temp_dict["date"] = Lesson.date.date
        temp_dict["lesson"] = (
            Lesson.subject.name if Lesson.subject is not None else None
        )
        if Lesson.room is not None:
            temp_dict["room"] = Lesson.room.code
        else:
            temp_dict["room"] = "-"
        temp_dict["visible"] = Lesson.visible
        temp_dict["changes"] = Lesson.changes
        temp_dict["group"] = Lesson.group
        temp_dict["reason"] = None
        temp_dict["teacher"] = (
            Lesson.teacher.display_name if Lesson.teacher is not None else None
        )
        temp_dict["from_to"] = (
            Lesson.time.displayed_time if Lesson.time is not None else None
        )
        if temp_dict["changes"] is None:
            temp_dict["changes"] = ""
        elif temp_dict["changes"].type == 1:
            temp_dict["lesson"] = f"Lekcja odwołana ({temp_dict['lesson']})"
            temp_dict["changes_info"] = f"Lekcja odwołana ({temp_dict['lesson']})"
            temp_dict["reason"] = changes[str(temp_dict["changes"].id)]["reason"]
        elif temp_dict["changes"].type == 2:
            temp_dict["lesson"] = f"{temp_dict['lesson']} (Zastępstwo)"
            temp_dict["teacher"] = changes[str(temp_dict["changes"].id)]["teacher"]
            temp_dict["reason"] = changes[str(temp_dict["changes"].id)]["reason"]
        elif temp_dict["changes"].type == 4:
            temp_dict["lesson"] = f"Lekcja odwołana ({temp_dict['lesson']})"
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
            student_info[
                "full_name"
            ] = f"{student.pupil.first_name} {student.pupil.last_name}"
            student_info["id"] = student.pupil.id
            student_info["class"] = ""  # Waiting for new API release
            student_info["school"] = student.school.name
    return student_info
