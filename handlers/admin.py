from datetime import datetime, timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import TEACHER_TIMEZONE

from database.queries import (
    archive_student,
    student_homework_stats,
    block_student,
    create_homework,
    count_submissions_to_review,     
    get_latest_batch_items,       
    get_oldest_pending_review_for_student,  
    list_submissions_to_review, 
    get_homework,
    get_latest_submission,
    get_student,
    list_active_students,
    list_archived_students,
    list_blocked_students,
    mark_homework_reviewed,
    unarchive_student,
    unblock_student,
    approve_student,
)

from keyboards.inline import (
    assign_student_picker_keyboard,
    blocked_list_keyboard,
    confirm_assignment_keyboard,
    deadline_picker_keyboard,
    to_review_student_list_keyboard,
    submission_review_keyboard,
    student_detail_keyboard,
    students_list_keyboard,
)

from keyboards.reply import (
    admin_menu,
    BTN_ASSIGN_HW,
    BTN_BLOCKED,
    BTN_COMMANDS,
    BTN_STUDENTS,
    BTN_TO_REVIEW,
)

from states.homework import AssignHomework, ReviewHomework
from utils.roles import IsAdmin
from utils.time_format import format_time_remaining

async def _safe_delete(bot: Bot, chat_id: int, message_id: int) -> None:
    """Delete a message, swallowing any error (too old, already gone, etc.)."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

@router.message(Command("start"))
async def cmd_start_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Teacher panel ready.",
        reply_markup=admin_menu(),
    )

# Canceling
@router.message(Command("cancel"))
async def cmd_cancel_admin(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Nothing to cancel.")
        return
    await state.clear()
    await message.answer("Cancelled.")


# ---------- /whoami ----------
@router.message(Command("help"))
async def cmd_help_admin(message: Message):
    text = (
        "<b>Teacher commands</b>\n\n"
        "/students — list your students\n"
        "/blocked — list blocked users\n"
        "/whoami — show your role\n"
        "/help — this message\n\n"
        "<i>More commands will appear as we build out features.</i>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("whoami"))
async def cmd_whoami_admin(message: Message):
    await message.answer("You are the admin (teacher).")


# ---------- /students ----------

async def _send_students_list(target: Message | CallbackQuery) -> None:
    """Shared helper — used by the /students command and the 'back' button."""
    students = await list_active_students()
    archived = await list_archived_students()

    if not students and not archived:
        text = "You don't have any students yet."
    else:
        lines = [f"<b>Active students:</b> {len(students)}"]
        if archived:
            lines.append(f"<b>Archived:</b> {len(archived)}")
        lines.append("")
        lines.append("Tap a name to manage.")
        text = "\n".join(lines)

    # Show active first, then archived
    all_for_buttons = students + archived
    keyboard = students_list_keyboard(all_for_buttons)

    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.message.edit_text(
            text, reply_markup=keyboard, parse_mode="HTML"
        )
        await target.answer()


@router.message(Command("students"))
async def cmd_students(message: Message):
    await _send_students_list(message)


@router.callback_query(F.data == "students:back")
async def cb_students_back(callback: CallbackQuery):
    await _send_students_list(callback)


@router.callback_query(F.data.startswith("student:"))
async def cb_student_detail(callback: CallbackQuery):
    student_id = int(callback.data.split(":", 1)[1])
    student = await get_student(student_id)
    if student is None:
        await callback.answer("Student not found.", show_alert=True)
        return

    username_part = f"@{student.username}" if student.username else "—"
    level_part = student.level or "not set"
    status_parts = []
    if not student.is_active:
        status_parts.append("🗄 archived")
    if student.is_blocked:
        status_parts.append("🚫 blocked")
    if not status_parts:
        status_parts.append("✅ active")
    status = ", ".join(status_parts)

    # Homework stats
    stats = await student_homework_stats(student_id)
    stats_line = (
        f"📚 Homework: {stats['total']} total — "
        f"{stats['pending']} pending, "
        f"{stats['submitted']} awaiting review, "
        f"{stats['reviewed']} reviewed"
    )

    text = (
        f"<b>{student.full_name}</b>\n\n"
        f"Username: {username_part}\n"
        f"Telegram ID: <code>{student.telegram_id}</code>\n"
        f"Level: {level_part}\n"
        f"Status: {status}\n"
        f"Joined: {student.created_at.strftime('%Y-%m-%d')}\n\n"
        f"{stats_line}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=student_detail_keyboard(
            student.telegram_id,
            is_archived=not student.is_active,
        ),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("archive:"))
async def cb_archive(callback: CallbackQuery):
    student_id = int(callback.data.split(":", 1)[1])
    student = await archive_student(student_id)
    if student is None:
        await callback.answer("Student not found.", show_alert=True)
        return
    await callback.answer(f"Archived {student.full_name}.")
    await _send_students_list(callback)

@router.callback_query(F.data.startswith("block:"))
async def cb_block(callback: CallbackQuery, bot: Bot):
    student_id = int(callback.data.split(":", 1)[1])
    student = await block_student(student_id)
    if student is None:
        await callback.answer("Student not found.", show_alert=True)
        return
    await callback.answer(f"Blocked {student.full_name}.")

    # Notify the student so they know they've been removed
    try:
        await bot.send_message(
            student_id,
            "You have been removed from the system by your teacher.",
        )
    except Exception:
        pass  # they may have blocked the bot, fine

    await _send_students_list(callback)


@router.callback_query(F.data.startswith("unarchive:"))
async def cb_unarchive(callback: CallbackQuery):
    student_id = int(callback.data.split(":", 1)[1])
    student = await unarchive_student(student_id)
    if student is None:
        await callback.answer("Student not found.", show_alert=True)
        return
    await callback.answer(f"Reactivated {student.full_name}.")
    await _send_students_list(callback)


# ---------- /blocked ----------

@router.message(Command("blocked"))
async def cmd_blocked(message: Message):
    blocked = await list_blocked_students()
    if not blocked:
        await message.answer("No blocked users.")
        return
    text = f"<b>Blocked users:</b> {len(blocked)}"
    await message.answer(
        text,
        reply_markup=blocked_list_keyboard(blocked),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("unblock:"))
async def cb_unblock(callback: CallbackQuery):
    student_id = int(callback.data.split(":", 1)[1])
    student = await unblock_student(student_id)
    if student is None:
        await callback.answer("User not found.", show_alert=True)
        return
    await callback.answer(f"Unblocked {student.full_name}.")
    # Refresh the blocked list
    blocked = await list_blocked_students()
    if not blocked:
        await callback.message.edit_text("No blocked users.")
    else:
        await callback.message.edit_text(
            f"<b>Blocked users:</b> {len(blocked)}",
            reply_markup=blocked_list_keyboard(blocked),
            parse_mode="HTML",
        )


# ---------- approval callbacks (from Step 1.4, now with blocking) ----------

@router.callback_query(F.data.startswith("approve:"))
async def cb_approve(callback: CallbackQuery, bot: Bot):
    student_id = int(callback.data.split(":", 1)[1])
    student = await approve_student(student_id)
    if student is None:
        await callback.answer("Student not found.", show_alert=True)
        return

    await callback.message.edit_text(
        f"✅ Approved: <b>{student.full_name}</b> "
        f"(<code>{student.telegram_id}</code>)",
        parse_mode="HTML",
    )
    await callback.answer("Approved!")

    try:
        from keyboards.reply import student_menu
        await bot.send_message(
            student.telegram_id,
            "🎉 You've been approved! Tap a button below to begin.",
            reply_markup=student_menu(),
        )
    except Exception as e:
        await bot.send_message(
            callback.from_user.id,
            f"⚠️ Couldn't notify student: {e}",
        )


@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(callback: CallbackQuery, bot: Bot):
    student_id = int(callback.data.split(":", 1)[1])
    student = await block_student(student_id)
    if student is None:
        await callback.answer("Student not found.", show_alert=True)
        return

    await callback.message.edit_text(
        f"🚫 Blocked: <b>{student.full_name}</b> "
        f"(<code>{student.telegram_id}</code>)",
        parse_mode="HTML",
    )
    await callback.answer("Blocked.")

    try:
        await bot.send_message(
            student_id,
            "Sorry, your registration was not accepted.",
        )
    except Exception:
        pass

@router.message(F.text == BTN_STUDENTS)
async def btn_students(message: Message):
    await cmd_students(message)


@router.message(F.text == BTN_BLOCKED)
async def btn_blocked(message: Message):
    await cmd_blocked(message)


@router.message(F.text == BTN_COMMANDS)
async def btn_commands(message: Message):
    await cmd_help_admin(message)



# =====================================================================
# Assign homework FSM
# =====================================================================

@router.message(F.text == BTN_ASSIGN_HW)
async def assign_hw_start(message: Message, state: FSMContext):
    """Entry point for assigning homework."""
    await state.clear()

    students = await list_active_students()
    if not students:
        await message.answer(
            "You don't have any active students to assign homework to."
        )
        return

    await message.answer(
        "📝 <b>Assign homework</b>\n\nWhich student is this for?",
        reply_markup=assign_student_picker_keyboard(students),
        parse_mode="HTML",
    )
    await state.set_state(AssignHomework.choosing_student)


@router.callback_query(AssignHomework.choosing_student, F.data.startswith("assignto:"))
async def assign_hw_student_picked(callback: CallbackQuery, state: FSMContext):
    student_id = int(callback.data.split(":", 1)[1])
    student = await get_student(student_id)
    if student is None:
        await callback.answer("Student not found.", show_alert=True)
        await state.clear()
        return

    await state.update_data(
        student_id=student.telegram_id,
        student_name=student.full_name,
    )

    await callback.message.edit_text(
        f"📝 Assigning homework to <b>{student.full_name}</b>\n\n"
        "Now type the task. Be specific — this is what the student will see.\n\n"
        "Example: <i>Read the article at [link] and write 5 sentences "
        "summarizing the main argument.</i>",
        parse_mode="HTML",
    )
    await callback.answer()
    await state.set_state(AssignHomework.typing_task)


@router.message(AssignHomework.typing_task, F.text)
async def assign_hw_task_received(message: Message, state: FSMContext):
    task = message.text.strip()
    if len(task) < 5:
        await message.answer("Task is too short. Please write a clear assignment.")
        return
    if len(task) > 2000:
        await message.answer("Task is too long (max 2000 characters).")
        return
    if task.startswith("/"):
        await message.answer("Please type the task, not a command.")
        return

    await state.update_data(task=task)

    data = await state.get_data()
    student_name = data["student_name"]

    await message.answer(
        f"Task for <b>{student_name}</b>:\n\n"
        f"<i>{task}</i>\n\n"
        "When is it due?",
        reply_markup=deadline_picker_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(AssignHomework.choosing_deadline)


@router.message(AssignHomework.typing_task)
async def assign_hw_task_wrong_type(message: Message):
    await message.answer("Please type the task as a text message.")


def _compute_deadline(preset: str) -> datetime | None:
    """Turn a preset string into an actual datetime (end of day, teacher tz).

    Returns None if `preset` is unrecognized.
    """
    now = datetime.now(TEACHER_TIMEZONE)
    today_eod = now.replace(hour=23, minute=59, second=0, microsecond=0)

    if preset == "today":
        return today_eod
    if preset == "tomorrow":
        return today_eod + timedelta(days=1)
    if preset == "3d":
        return today_eod + timedelta(days=3)
    if preset == "1w":
        return today_eod + timedelta(days=7)
    return None


@router.callback_query(
    AssignHomework.choosing_deadline,
    F.data.startswith("deadline:"),
)
async def assign_hw_deadline_picked(callback: CallbackQuery, state: FSMContext):
    preset = callback.data.split(":", 1)[1]

    if preset == "custom":
        await callback.message.edit_text(
            "📅 Type the due date in format <code>YYYY-MM-DD</code>\n\n"
            "Example: <code>2026-04-20</code>\n\n"
            "The deadline will be end of that day (23:59) "
            f"in your timezone ({TEACHER_TIMEZONE}).",
            parse_mode="HTML",
        )
        await callback.answer()
        await state.set_state(AssignHomework.typing_custom_date)
        return

    deadline = _compute_deadline(preset)
    if deadline is None:
        await callback.answer("Unknown deadline option.", show_alert=True)
        return

    await state.update_data(deadline=deadline.isoformat())
    await _show_confirmation(callback, state)


@router.message(AssignHomework.typing_custom_date, F.text)
async def assign_hw_custom_date(message: Message, state: FSMContext):
    raw = message.text.strip()
    try:
        date_part = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        await message.answer(
            "That's not a valid date. Please use format <code>YYYY-MM-DD</code>, "
            "for example <code>2026-04-20</code>.",
            parse_mode="HTML",
        )
        return

    # Build end-of-day in teacher timezone
    deadline = date_part.replace(
        hour=23, minute=59, second=0, microsecond=0, tzinfo=TEACHER_TIMEZONE
    )

    # Reject deadlines in the past
    now = datetime.now(TEACHER_TIMEZONE)
    if deadline < now:
        await message.answer("That date is in the past. Pick a future date.")
        return

    await state.update_data(deadline=deadline.isoformat())
    await _show_confirmation(message, state)


async def _show_confirmation(
    target: Message | CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    student_name = data["student_name"]
    task = data["task"]
    deadline = datetime.fromisoformat(data["deadline"])

    # Format deadline nicely for display
    deadline_str = deadline.strftime("%Y-%m-%d %H:%M")

    text = (
        "📝 <b>Confirm assignment</b>\n\n"
        f"Student: <b>{student_name}</b>\n"
        f"Deadline: <b>{deadline_str}</b>\n\n"
        f"Task:\n<i>{task}</i>"
    )

    keyboard = confirm_assignment_keyboard()

    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await target.answer()

    await state.set_state(AssignHomework.confirming)


@router.callback_query(AssignHomework.confirming, F.data == "assign:confirm")
async def assign_hw_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    student_id = data["student_id"]
    student_name = data["student_name"]
    task = data["task"]
    deadline = datetime.fromisoformat(data["deadline"])

    # Create the homework in the database
    hw = await create_homework(
        student_id=student_id,
        task=task,
        deadline=deadline,
    )

    await state.clear()

    await callback.message.edit_text(
        f"✅ Homework #{hw.id} assigned to <b>{student_name}</b>.",
        parse_mode="HTML",
    )
    await callback.answer("Assigned!")

    # Deliver the homework to the student
    try:
        from keyboards.inline import new_homework_keyboard
        time_remaining = format_time_remaining(deadline)
        await bot.send_message(
            student_id,
            f"📝 <b>New homework #{hw.id}</b>\n\n"
            f"You have a new homework from your teacher.\n"
            f"{time_remaining}",
            reply_markup=new_homework_keyboard(hw.id),
            parse_mode="HTML",
        )
    except Exception as e:
        await bot.send_message(
            callback.from_user.id,
            f"⚠️ Couldn't notify student: {e}",
        )

@router.callback_query(F.data == "assign:cancel")
async def assign_hw_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Assignment cancelled.")
    await callback.answer()


# =====================================================================
# Review submissions
# =====================================================================
@router.callback_query(F.data.startswith("review:mark:"))
async def cb_review_mark(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Mark a homework as reviewed, leave a trace, and auto-advance."""
    homework_id = int(callback.data.split(":")[2])

    hw = await mark_homework_reviewed(homework_id=homework_id, feedback=None)
    if hw is None:
        await callback.answer("Homework not found.", show_alert=True)
        return

    # Clean up the current review messages
    await _cleanup_current_review(bot, state)

    # Leave a trace marker
    await bot.send_message(
        callback.from_user.id,
        f"✅ #{hw.id} reviewed",
    )

    # Notify the student
    try:
        await bot.send_message(
            hw.student_id,
            f"✅ Your teacher marked homework #{hw.id} as reviewed.",
        )
    except Exception:
        pass

    await callback.answer("Marked reviewed.")
    await _send_next_submission_for_student(callback, bot, hw.student_id, state)


@router.callback_query(F.data.startswith("review:feedback:"))
async def cb_review_feedback_start(callback: CallbackQuery, state: FSMContext):
    """Begin the review-with-feedback flow."""
    homework_id = int(callback.data.split(":")[2])

    hw = await get_homework(homework_id)
    if hw is None:
        await callback.answer("Homework not found.", show_alert=True)
        return

    student = await get_student(hw.student_id)
    student_name = student.full_name if student else "Unknown"

    await state.update_data(homework_id=homework_id)
    await state.set_state(ReviewHomework.typing_feedback)

    prompt_msg = await callback.message.answer(
        f"💬 Type your feedback for <b>{escape(student_name)}</b>'s homework #{homework_id}.\n\n"
        "This message will be sent to the student along with the reviewed mark.\n"
        "Send /cancel to stop.",
        parse_mode="HTML",
    )
    # Remember the prompt so we can delete it once feedback is processed
    await state.update_data(feedback_prompt_msg_id=prompt_msg.message_id)

    await callback.answer()


@router.message(ReviewHomework.typing_feedback, Command("cancel"))
async def cb_review_feedback_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Review cancelled.")

@router.callback_query(F.data.startswith("review:open:"))
async def cb_review_open(callback: CallbackQuery, bot: Bot):
    """Open a specific submission for review (from a push notification)."""
    homework_id = int(callback.data.split(":")[2])

    hw = await get_homework(homework_id)
    if hw is None:
        await callback.answer("Homework not found.", show_alert=True)
        return
    if hw.status == "reviewed":
        await callback.answer("This submission has already been reviewed.", show_alert=True)
        return

    # Delete the notification card — it's served its purpose
    await _safe_delete(bot, callback.from_user.id, callback.message.message_id)

    sent = await _send_review_for_homework(callback, bot, homework_id)
    if not sent:
        await callback.answer("Submission missing.", show_alert=True)


@router.message(ReviewHomework.typing_feedback, F.text)
async def cb_review_feedback_received(
    message: Message,
    state: FSMContext,
    bot: Bot,
):
    feedback = message.text.strip()
    if feedback.startswith("/"):
        await message.answer(
            "Please type your feedback as a regular message. Use /cancel to stop."
        )
        return
    if len(feedback) < 2:
        await message.answer("That's too short. Please write real feedback.")
        return

    data = await state.get_data()
    homework_id = data.get("homework_id")
    if homework_id is None:
        await message.answer("Something went wrong. Please tap review again.")
        await state.clear()
        return

    # Delete the "type your feedback" prompt
    prompt_id = data.get("feedback_prompt_msg_id")
    if prompt_id:
        await _safe_delete(bot, message.chat.id, prompt_id)

    # Also delete the student's own typed feedback message (optional but tidy)
    await _safe_delete(bot, message.chat.id, message.message_id)

    hw = await mark_homework_reviewed(
        homework_id=homework_id,
        feedback=feedback,
    )

    if hw is None:
        await message.answer("Homework not found.")
        await state.clear()
        return

    # Clean up the current review messages (before clearing state)
    await _cleanup_current_review(bot, state)
    await state.clear()

    # Leave a trace marker
    await message.answer(f"✅ #{homework_id} reviewed with feedback")

    try:
        await bot.send_message(
            hw.student_id,
            f"✅ <b>Homework #{hw.id} reviewed</b>\n\n"
            f"Your teacher left this feedback:\n\n"
            f"<i>{escape(feedback)}</i>",
            parse_mode="HTML",
        )
    except Exception:
        pass

    next_hw = await get_oldest_pending_review_for_student(hw.student_id)
    if next_hw is not None:
        await message.answer(
            "More from this student waiting — tap 🔔 To review to continue."
        )
    else:
        remaining = await count_submissions_to_review()
        if remaining == 0:
            await message.answer("No more submissions to review! 🎉")
        else:
            await message.answer(
                f"{remaining} other submission(s) still waiting — "
                f"tap 🔔 To review to continue."
            )

@router.message(ReviewHomework.typing_feedback)
async def cb_review_feedback_wrong_type(message: Message):
    await message.answer("Please type your feedback as a text message.")


# =====================================================================
# Global "To review" flow
# =====================================================================

@router.message(F.text == BTN_TO_REVIEW)
async def btn_to_review(message: Message, state: FSMContext):
    await state.clear()
    await _show_review_student_list(message, state)


async def _show_review_student_list(
    target: Message | CallbackQuery,
    state: FSMContext | None = None,
) -> None:
    """Show the list of students with homeworks awaiting review."""
    items = await list_submissions_to_review()

    # Resolve bot + chat_id for potential cleanup
    if isinstance(target, Message):
        chat_id = target.chat.id
        bot = target.bot
    else:
        chat_id = target.from_user.id
        bot = target.bot

    # Delete previous list message if we have one
    if state is not None:
        data = await state.get_data()
        prev_id = data.get("review_list_msg_id")
        if prev_id:
            await _safe_delete(bot, chat_id, prev_id)

    if not items:
        text = "🔔 <b>To review</b>\n\nNothing to review right now! 🎉"
        if isinstance(target, Message):
            sent = await target.answer(text, parse_mode="HTML")
        else:
            sent = await target.message.answer(text, parse_mode="HTML")
            await target.answer()
        if state is not None:
            await state.update_data(review_list_msg_id=sent.message_id)
        return

    # Group by student, preserving order of first appearance
    grouped: dict[int, list] = {}
    for hw, student, _ in items:
        if student.telegram_id not in grouped:
            grouped[student.telegram_id] = [student, 0]
        grouped[student.telegram_id][1] += 1

    seen = set()
    ordered = []
    for _, student, _ in items:
        if student.telegram_id in seen:
            continue
        seen.add(student.telegram_id)
        count = grouped[student.telegram_id][1]
        ordered.append((student, count))

    total = len(items)
    lines = [
        f"🔔 <b>To review</b> — {total} submission{'s' if total != 1 else ''}",
        "",
        "Oldest waiting first. Tap a student to start reviewing.",
    ]
    text = "\n".join(lines)
    keyboard = to_review_student_list_keyboard(ordered)

    if isinstance(target, Message):
        sent = await target.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        sent = await target.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await target.answer()

    if state is not None:
        await state.update_data(review_list_msg_id=sent.message_id)


@router.callback_query(F.data.startswith("review:student:"))
async def cb_review_student_start(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
):
    student_id = int(callback.data.split(":")[2])

    # Delete the student list — we're leaving the "choose student" screen
    data = await state.get_data()
    list_id = data.get("review_list_msg_id")
    if list_id:
        await _safe_delete(bot, callback.from_user.id, list_id)
        await state.update_data(review_list_msg_id=None)

    await _send_next_submission_for_student(callback, bot, student_id, state)


async def _send_review_for_homework(
    callback_or_chat_id,
    bot: Bot,
    homework_id: int,
    state: FSMContext | None = None,
) -> bool:
    """Send the review UI for a homework (header + all batch items + buttons)."""
    hw = await get_homework(homework_id)
    if hw is None:
        return False

    student = await get_student(hw.student_id)
    if student is None:
        return False

    items = await get_latest_batch_items(hw.id)
    if not items:
        return False

    latest_time = max(item.submitted_at for item in items)
    any_late = any(item.is_late for item in items)

    late_tag = " ⚠️ LATE" if any_late else ""
    submitted_str = latest_time.strftime("%Y-%m-%d %H:%M")

    safe_task = escape(hw.task[:200]) + ("…" if len(hw.task) > 200 else "")
    safe_name = escape(student.full_name)

    header_text = (
        f"📋 <b>Reviewing</b>{late_tag}\n\n"
        f"Student: <b>{safe_name}</b>\n"
        f"Homework: #{hw.id}\n"
        f"Task: <i>{safe_task}</i>\n"
        f"Submitted: {submitted_str}\n"
        f"Items: {len(items)}"
    )

    # Resolve chat ID
    if isinstance(callback_or_chat_id, CallbackQuery):
        chat_id = callback_or_chat_id.from_user.id
        await callback_or_chat_id.answer()
    else:
        chat_id = callback_or_chat_id

    # Send the header (no buttons on it)
    header_msg = await bot.send_message(chat_id, header_text, parse_mode="HTML")

    # Send each item. The review buttons go on the LAST message only,
    # so the teacher can see all items before acting.
    review_kb = submission_review_keyboard(hw.id)
    content_msg_ids = []

    for idx, sub in enumerate(items):
        is_last = idx == len(items) - 1
        kb = review_kb if is_last else None

        if sub.content_type == "text":
            raw = sub.content[:1500] + ("…" if len(sub.content) > 1500 else "")
            preview = escape(raw)
            msg = await bot.send_message(
                chat_id,
                f"<i>{preview}</i>",
                reply_markup=kb,
                parse_mode="HTML",
            )
        elif sub.content_type == "voice":
            msg = await bot.send_voice(
                chat_id,
                voice=sub.content,
                caption=sub.caption,
                reply_markup=kb,
            )
        elif sub.content_type == "photo":
            msg = await bot.send_photo(
                chat_id,
                photo=sub.content,
                caption=sub.caption,
                reply_markup=kb,
            )
        else:
            continue

        content_msg_ids.append(msg.message_id)

    # Track for cleanup
    if state is not None:
        await state.update_data(
            current_review_header_id=header_msg.message_id,
            current_review_content_ids=content_msg_ids,
            current_review_chat_id=chat_id,
        )

    return True

async def _cleanup_current_review(bot: Bot, state: FSMContext) -> None:
    """Delete the header + content messages of the current review, if any."""
    data = await state.get_data()
    chat_id = data.get("current_review_chat_id")
    header_id = data.get("current_review_header_id")
    content_ids = data.get("current_review_content_ids", [])

    if chat_id is None:
        return

    if header_id is not None:
        await _safe_delete(bot, chat_id, header_id)
    for cid in content_ids:
        await _safe_delete(bot, chat_id, cid)

    await state.update_data(
        current_review_header_id=None,
        current_review_content_ids=[],
    )

async def _send_next_submission_for_student(
    callback: CallbackQuery,
    bot: Bot,
    student_id: int,
    state: FSMContext,
) -> None:
    """Fetch and send the oldest pending submission for this student."""
    data = await state.get_data()
    skipped: set[int] = set(data.get("review_skipped", []))

    hw = await get_oldest_pending_review_for_student(
        student_id,
        exclude_ids=skipped,
    )

    if hw is None:
        await state.update_data(review_skipped=[])
        await callback.answer("All caught up on this student!", show_alert=False)
        await _show_review_student_list(callback, state)
        return

    sent = await _send_review_for_homework(callback, bot, hw.id, state)
    if not sent:
        await callback.answer("Submission missing.", show_alert=True)

@router.callback_query(F.data.startswith("review:skip:"))
async def cb_review_skip(callback: CallbackQuery, bot: Bot, state: FSMContext):
    homework_id = int(callback.data.split(":")[2])
    hw = await get_homework(homework_id)
    if hw is None:
        await callback.answer("Homework not found.", show_alert=True)
        return

    # Record skip in session state
    data = await state.get_data()
    skipped = set(data.get("review_skipped", []))
    skipped.add(homework_id)
    await state.update_data(review_skipped=list(skipped))

    # Clean up current review messages
    await _cleanup_current_review(bot, state)

    # Leave a trace marker
    await bot.send_message(
        callback.from_user.id,
        f"⏭ #{hw.id} skipped",
    )

    await callback.answer("Skipped — you can come back to it later.")
    await _send_next_submission_for_student(callback, bot, hw.student_id, state)