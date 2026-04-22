from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import Student


def approval_keyboard(student_telegram_id: int) -> InlineKeyboardMarkup:
    """Approve / Reject buttons for a pending student."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Approve",
                    callback_data=f"approve:{student_telegram_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Reject",
                    callback_data=f"reject:{student_telegram_id}",
                ),
            ]
        ]
    )


def students_list_keyboard(students: list[Student]) -> InlineKeyboardMarkup:
    """One button per student, tapping opens their detail view."""
    if not students:
        return InlineKeyboardMarkup(inline_keyboard=[])

    rows = [
        [
            InlineKeyboardButton(
                text=s.full_name,
                callback_data=f"student:{s.telegram_id}",
            )
        ]
        for s in students
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def student_detail_keyboard(
    student_telegram_id: int,
    is_archived: bool,
) -> InlineKeyboardMarkup:
    """Action buttons for a single student's detail view."""
    if is_archived:
        primary = InlineKeyboardButton(
            text="♻️ Unarchive",
            callback_data=f"unarchive:{student_telegram_id}",
        )
    else:
        primary = InlineKeyboardButton(
            text="🗄 Archive",
            callback_data=f"archive:{student_telegram_id}",
        )

    block_btn = InlineKeyboardButton(
        text="🚫 Block",
        callback_data=f"block:{student_telegram_id}",
    )
    back_btn = InlineKeyboardButton(
        text="« Back",
        callback_data="students:back",
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [primary, block_btn],
            [back_btn],
        ]
    )


def blocked_list_keyboard(students: list[Student]) -> InlineKeyboardMarkup:
    """One row per blocked user with an Unblock button."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"♻️ Unblock {s.full_name}",
                callback_data=f"unblock:{s.telegram_id}",
            )
        ]
        for s in students
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def level_keyboard() -> InlineKeyboardMarkup:
    """Inline buttons for selecting CEFR level during registration."""
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    row = [
        InlineKeyboardButton(text=lvl, callback_data=f"reglevel:{lvl}")
        for lvl in levels
    ]
    # Two rows of 3 looks cleaner than one row of 6
    return InlineKeyboardMarkup(inline_keyboard=[row[:3], row[3:]])


def assign_student_picker_keyboard(students: list[Student]) -> InlineKeyboardMarkup:
    """Inline keyboard to pick which student to assign homework to."""
    rows = [
        [
            InlineKeyboardButton(
                text=s.full_name,
                callback_data=f"assignto:{s.telegram_id}",
            )
        ]
        for s in students
    ]
    rows.append([
        InlineKeyboardButton(text="« Cancel", callback_data="assign:cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def deadline_picker_keyboard() -> InlineKeyboardMarkup:
    """Preset deadline options for a new homework."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Today", callback_data="deadline:today"),
                InlineKeyboardButton(text="Tomorrow", callback_data="deadline:tomorrow"),
            ],
            [
                InlineKeyboardButton(text="In 3 days", callback_data="deadline:3d"),
                InlineKeyboardButton(text="In 1 week", callback_data="deadline:1w"),
            ],
            [
                InlineKeyboardButton(text="📅 Custom date", callback_data="deadline:custom"),
            ],
            [
                InlineKeyboardButton(text="« Cancel", callback_data="assign:cancel"),
            ],
        ]
    )


def confirm_assignment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data="assign:confirm"),
                InlineKeyboardButton(text="« Cancel", callback_data="assign:cancel"),
            ]
        ]
    )


def student_homework_list_keyboard(
    homeworks: list,
    show_history_button: bool = True,
) -> InlineKeyboardMarkup:
    """Active homework list. History button at the bottom."""
    rows = []
    for hw in homeworks:
        preview = hw.task[:40] + ("…" if len(hw.task) > 40 else "")
        rows.append([
            InlineKeyboardButton(
                text=f"#{hw.id}: {preview}",
                callback_data=f"hw:view:{hw.id}",
            )
        ])
    if show_history_button:
        rows.append([
            InlineKeyboardButton(
                text="📜 View history",
                callback_data="hw:history",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def student_homework_history_keyboard(homeworks: list) -> InlineKeyboardMarkup:
    """Reviewed homework list with a back-to-active button."""
    rows = []
    for hw in homeworks:
        preview = hw.task[:40] + ("…" if len(hw.task) > 40 else "")
        rows.append([
            InlineKeyboardButton(
                text=f"✅ {preview}",
                callback_data=f"hw:view:{hw.id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="« Back to active",
            callback_data="hw:list",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def homework_detail_keyboard(
    homework_id: int,
    already_submitted: bool,
    is_reviewed: bool = False,
) -> InlineKeyboardMarkup:
    """Detail view for a single homework."""
    rows = []
    if not is_reviewed:
        submit_label = "✍️ Resubmit" if already_submitted else "✍️ Submit"
        rows.append([
            InlineKeyboardButton(
                text=submit_label,
                callback_data=f"hw:submit:{homework_id}",
            ),
        ])
    rows.append([
        InlineKeyboardButton(
            text="« Back to list",
            callback_data="hw:list",
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def submission_review_keyboard(homework_id: int) -> InlineKeyboardMarkup:
    """Attached to submission messages during review."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Mark reviewed",
                    callback_data=f"review:mark:{homework_id}",
                ),
                InlineKeyboardButton(
                    text="💬 With feedback",
                    callback_data=f"review:feedback:{homework_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏭ Skip for now",
                    callback_data=f"review:skip:{homework_id}",
                ),
            ],
        ]
    )

def new_homework_keyboard(homework_id: int) -> InlineKeyboardMarkup:
    """Single 'Open homework' button for new-assignment notifications."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="📖 Open homework",
                callback_data=f"hw:view:{homework_id}",
            )
        ]]
    )

def to_review_student_list_keyboard(
    students_with_counts: list[tuple],  # (student, count) pairs
) -> InlineKeyboardMarkup:
    """List of students who have submissions awaiting review."""
    rows = []
    for student, count in students_with_counts:
        rows.append([
            InlineKeyboardButton(
                text=f"{student.full_name} ({count})",
                callback_data=f"review:student:{student.telegram_id}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def submission_notification_keyboard(homework_id: int) -> InlineKeyboardMarkup:
    """Single 'Open' button for push submission notifications."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="📖 Open",
                callback_data=f"review:open:{homework_id}",
            )
        ]]
    )


def submission_preview_keyboard() -> InlineKeyboardMarkup:
    """Buttons on the 'your submission so far' preview after each item."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Done", callback_data="submit:done")],
            [InlineKeyboardButton(text="✏️ Edit items", callback_data="submit:edit")],
            [InlineKeyboardButton(text="« Cancel", callback_data="submit:cancel")],
        ]
    )


def submission_edit_keyboard(items: list) -> InlineKeyboardMarkup:
    """Per-item delete buttons + add more + back.

    `items` is a list of dicts with keys: 'index' (1-based), 'label' (short preview).
    """
    rows = []
    for item in items:
        rows.append([
            InlineKeyboardButton(
                text=f"❌ Remove {item['index']}. {item['label']}",
                callback_data=f"submit:remove:{item['index'] - 1}",  # 0-based internally
            )
        ])
    rows.append([
        InlineKeyboardButton(text="➕ Add more", callback_data="submit:addmore")
    ])
    rows.append([
        InlineKeyboardButton(text="« Back", callback_data="submit:back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)