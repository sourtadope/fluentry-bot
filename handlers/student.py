from aiogram import Bot, F, Router
from html import escape
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_ID

from database.queries import (
    create_student,
    get_student,
    set_student_level,
    list_student_homework_active,
    list_student_homework_reviewed,
    get_homework,
    get_latest_submission,
    add_submission,          
)

from keyboards.inline import (
    approval_keyboard,
    level_keyboard,
    student_homework_list_keyboard,
    student_homework_history_keyboard,
    homework_detail_keyboard,
)

from keyboards.reply import (
    student_menu,
    remove_menu,
    BTN_HOMEWORK,
    BTN_VOCAB,
    BTN_PROGRESS,
    BTN_PROFILE,
    BTN_REPORT,
)

from states.registration import Registration
from states.homework import SubmitHomework   # NEW
from utils.roles import IsNotAdmin
from utils.time_format import format_time_remaining

async def _safe_delete_message(bot: Bot, chat_id: int, message_id: int) -> None:
    """Delete a message, swallowing any error."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

def _format_item_label(item: dict, index: int) -> str:
    """Short label for a submission item in preview or edit lists."""
    item_type = item["type"]
    if item_type == "text":
        preview = item["content"][:30].replace("\n", " ")
        if len(item["content"]) > 30:
            preview += "…"
        return f"📝 \"{preview}\""
    if item_type == "voice":
        return "🎙 Voice message"
    if item_type == "photo":
        return "🖼 Photo"
    return "Unknown"


def _build_preview_text(task: str, items: list[dict]) -> str:
    """The 'your submission so far' message content."""
    lines = [
        f"📝 <b>Homework</b>\n\n<i>{escape(task)}</i>\n",
        f"📦 <b>Your submission so far</b> — {len(items)} item{'s' if len(items) != 1 else ''}:",
        "",
    ]
    for i, item in enumerate(items, start=1):
        lines.append(f"{i}. {_format_item_label(item, i)}")
    lines.append("")
    lines.append("Send more items, or tap <b>Done</b> when finished.")
    return "\n".join(lines)

async def _start_collecting(
    message: Message,
    state: FSMContext,
    hw,
    first_time: bool = True,
) -> None:
    """Send the initial collecting prompt and put student in collecting state."""
    time_str = format_time_remaining(hw.deadline)
    safe_task = escape(hw.task)

    if first_time:
        text = (
            f"📝 <b>Homework #{hw.id}</b>\n\n"
            f"{safe_task}\n\n"
            f"{time_str}\n\n"
            f"✍️ <b>Send your answer below</b>\n"
            f"You can send any combination of text, voice messages, or photos. "
            f"After each item you'll see a preview with a Done button.\n\n"
            f"Send /cancel to stop."
        )
    else:
        text = (
            f"✍️ Send another item, or tap Done when finished.\n"
            f"Send /cancel to stop."
        )

    await message.answer(text, parse_mode="HTML")
    await state.set_state(SubmitHomework.collecting)

async def _require_active_student(message: Message):
    """Fetch the student and verify they're allowed to use the bot.

    Returns the Student if allowed, otherwise replies with the right
    message, removes the reply keyboard, and returns None.
    """
    student = await get_student(message.from_user.id)

    if student is None:
        await message.answer(
            "You're not registered. Send /start to begin.",
            reply_markup=remove_menu(),
        )
        return None

    if student.is_blocked:
        await message.answer(
            "Your access to this bot has been revoked.",
            reply_markup=remove_menu(),
        )
        return None

    if not student.is_approved:
        await message.answer(
            "You're still waiting for teacher approval.",
            reply_markup=remove_menu(),
        )
        return None

    if not student.is_active:
        await message.answer(
            "Your account is archived. Contact your teacher.",
            reply_markup=remove_menu(),
        )
        return None

    return student


async def _require_active_student_cb(callback: CallbackQuery):
    """Callback version of _require_active_student."""
    student = await get_student(callback.from_user.id)

    if (
        student is None
        or student.is_blocked
        or not student.is_approved
        or not student.is_active
    ):
        await callback.answer(
            "You don't have access to this action.",
            show_alert=True,
        )
        return None

    return student


router = Router()
router.message.filter(IsNotAdmin())
router.callback_query.filter(IsNotAdmin())


# ---------- /start ----------

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Entry point for students.

    Behaviour depends on the user's current status in the database.
    Any existing FSM state is cleared on every /start so users can
    always restart the flow by sending /start again.
    """
    await state.clear()

    user = message.from_user
    if user is None:
        return

    existing = await get_student(user.id)

    if existing is not None and existing.is_blocked:
        await message.answer("Your registration request was declined.")
        return

    if existing is not None and existing.is_approved and existing.is_active:
        await message.answer(
            f"👋 Welcome back, {existing.full_name}!",
            reply_markup=student_menu(),
        )
        return

    if existing is not None and existing.is_approved and not existing.is_active:
        await message.answer(
            "Your account is currently archived. Contact your teacher."
        )
        return

    if existing is not None and not existing.is_approved:
        await message.answer(
            "⏳ You're still waiting for teacher approval. Please be patient!"
        )
        return

    # Brand new user — start the registration FSM
    await message.answer(
        "👋 Welcome to the English school bot!\n\n"
        "Let's get you registered. First — what's your full name? "
        "(first and last, the name I should use for you in class)"
    )
    await state.set_state(Registration.waiting_for_name)

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Nothing to cancel.")
        return
    await state.clear()
    await message.answer("Cancelled. Send /start if you want to begin again.")


# ---------- FSM: waiting for name ----------

@router.message(Registration.waiting_for_name, F.text)
async def reg_got_name(message: Message, state: FSMContext):
    name = message.text.strip()

    # Basic sanity checks
    if len(name) < 2:
        await message.answer("That seems too short. Please type your full name.")
        return
    if len(name) > 80:
        await message.answer("That's too long. Please type your full name (under 80 characters).")
        return
    if name.startswith("/"):
        await message.answer("Please type your name, not a command.")
        return

    # Character check: only letters, spaces, hyphens, apostrophes.
    # Unicode-aware, so Cyrillic/accented names work fine.
    allowed_extras = {" ", "-", "'"}
    if not all(ch.isalpha() or ch in allowed_extras for ch in name):
        await message.answer(
            "Names should only contain letters. "
            "Please type your real full name."
        )
        return

    # Must contain at least one actual letter (prevents "   " or "---")
    if not any(ch.isalpha() for ch in name):
        await message.answer("Please type your real name.")
        return

    await state.update_data(full_name=name)
    await message.answer(
        f"Nice to meet you, {name}!\n\n"
        "What's your current English level?",
        reply_markup=level_keyboard(),
    )
    await state.set_state(Registration.waiting_for_level)


@router.message(Registration.waiting_for_name)
async def reg_name_wrong_type(message: Message):
    """Fires if user sends something that isn't text (e.g. a sticker) while we need their name."""
    await message.answer("Please type your name as a text message.")


# ---------- FSM: waiting for level ----------

@router.callback_query(Registration.waiting_for_level, F.data.startswith("reglevel:"))
async def reg_got_level(callback: CallbackQuery, state: FSMContext, bot: Bot):
    level = callback.data.split(":", 1)[1]

    data = await state.get_data()
    full_name = data.get("full_name")
    if not full_name:
        # Shouldn't happen, but just in case FSM data got lost
        await callback.answer("Something went wrong. Please send /start again.", show_alert=True)
        await state.clear()
        return

    user = callback.from_user

    # Create the student record
    student = await create_student(
        telegram_id=user.id,
        full_name=full_name,
        username=user.username,
    )
    # Store the level too (create_student doesn't take it as a parameter,
    # so we update it here — or we could extend create_student. Keeping it
    # simple for now.)
    await set_student_level(user.id, level)

    await state.clear()

    await callback.message.edit_text(
        f"✅ Got it! Your registration request has been sent to the teacher.\n\n"
        f"Name: <b>{full_name}</b>\n"
        f"Level: <b>{level}</b>\n\n"
        "You'll receive a message here once you're approved.",
        parse_mode="HTML",
    )
    await callback.answer()

    # Notify admin
    username_part = f" (@{user.username})" if user.username else ""
    await bot.send_message(
        ADMIN_ID,
        f"🔔 New registration request:\n\n"
        f"<b>{full_name}</b>{username_part}\n"
        f"Level: <b>{level}</b>\n"
        f"ID: <code>{user.id}</code>",
        reply_markup=approval_keyboard(user.id),
        parse_mode="HTML",
    )


# ---------- /whoami ----------

@router.message(Command("whoami"))
async def cmd_whoami(message: Message):
    student = await get_student(message.from_user.id)
    if student is None:
        await message.answer("You're not registered yet. Send /start to begin.")
    elif not student.is_approved:
        await message.answer("You're registered but waiting for approval.")
    else:
        await message.answer(f"You are {student.full_name}, an approved student.")

@router.message(Command("help"))
async def cmd_help_student(message: Message):
    student = await get_student(message.from_user.id)
    if student is None or not student.is_approved:
        await message.answer(
            "You're not registered yet. Send /start to begin."
        )
        return

    text = (
        f"Hi {student.full_name}! Here's what I can do:\n\n"
        "/whoami — show your info\n"
        "/cancel — cancel the current action\n"
        "/help — this message\n\n"
        "<i>Homework, vocab, and speaking practice are coming soon.</i>"
    )
    await message.answer(text, parse_mode="HTML")

# ---------- Reply keyboard button handlers ----------


@router.message(F.text == BTN_PROFILE)
async def btn_profile(message: Message):
    student = await _require_active_student(message)
    if student is None:
        return

    level = student.level or "not set"
    joined = student.created_at.strftime("%Y-%m-%d")
    username = f"@{student.username}" if student.username else "—"

    text = (
        "<b>👤 Your Profile</b>\n\n"
        f"Name: <b>{student.full_name}</b>\n"
        f"Username: {username}\n"
        f"Level: <b>{level}</b>\n"
        f"Joined: {joined}\n\n"
        "<b>Progress</b> <i>(coming soon)</i>\n"
        "📚 Homework completed: —\n"
        "📖 Words learned: —\n"
        "🔥 Current streak: —"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == BTN_REPORT)
async def btn_report(message: Message):
    student = await _require_active_student(message)
    if student is None:
        return
    await message.answer(
        "📨 <b>Report an issue</b>\n\n"
        "This feature is coming soon. For now, please message your teacher "
        "directly on Telegram if something's wrong with the bot.",
        parse_mode="HTML",
    )


@router.message(F.text == BTN_HOMEWORK)
async def btn_homework(message: Message):
    student = await _require_active_student(message)
    if student is None:
        return
    await _show_homework_list(message)


@router.message(F.text == BTN_VOCAB)
async def btn_vocab(message: Message):
    student = await _require_active_student(message)
    if student is None:
        return
    await message.answer("📖 Vocab is coming in Phase 5.")


@router.message(F.text == BTN_PROGRESS)
async def btn_progress(message: Message):
    student = await _require_active_student(message)
    if student is None:
        return
    await message.answer(
        "📊 Detailed progress stats are coming soon. "
        "For now, check your Profile for a summary."
    )


# ---------- Homework list rendering (shared) ----------

async def _show_homework_list(target: Message | CallbackQuery) -> None:
    """Render the student's active homework list."""
    user_id = target.from_user.id
    homeworks = await list_student_homework_active(user_id)

    if not homeworks:
        text = "📚 <b>Your homework</b>\n\nNo active homework right now! 🎉"
        # Still let them reach history from the empty state
        keyboard = student_homework_list_keyboard([], show_history_button=True)
    else:
        lines = ["📚 <b>Your homework</b>", ""]
        for i, hw in enumerate(homeworks, start=1):
            preview = hw.task[:60] + ("…" if len(hw.task) > 60 else "")
            time_str = format_time_remaining(hw.deadline)
            lines.append(f"<b>{i}.</b> {preview}")
            lines.append(f"   {time_str}")
            lines.append("")
        text = "\n".join(lines).rstrip()
        keyboard = student_homework_list_keyboard(homeworks)

    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await target.answer()


# ---------- Homework callback handlers ----------

@router.callback_query(F.data == "hw:list")
async def cb_hw_list(callback: CallbackQuery):
    student = await _require_active_student_cb(callback)
    if student is None:
        return
    await _show_homework_list(callback)

@router.callback_query(F.data == "hw:history")
async def cb_hw_history(callback: CallbackQuery):
    student = await _require_active_student_cb(callback)
    if student is None:
        return

    homeworks = await list_student_homework_reviewed(callback.from_user.id)

    if not homeworks:
        text = (
            "📜 <b>Homework history</b>\n\n"
            "No reviewed homework yet. Once your teacher reviews your "
            "submissions, they'll show up here."
        )
    else:
        lines = ["📜 <b>Homework history</b>", ""]
        for hw in homeworks:
            preview = hw.task[:60] + ("…" if len(hw.task) > 60 else "")
            lines.append(f"✅ {preview}")
        text = "\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=student_homework_history_keyboard(homeworks),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("hw:view:"))
async def cb_hw_view(callback: CallbackQuery):
    student = await _require_active_student_cb(callback)
    if student is None:
        return

    homework_id = int(callback.data.split(":")[2])

    hw = await get_homework(homework_id)
    if hw is None:
        await callback.answer("Homework not found.", show_alert=True)
        return

    if hw.student_id != callback.from_user.id:
        await callback.answer("Not your homework.", show_alert=True)
        return

    latest_sub = await get_latest_submission(homework_id)
    already_submitted = latest_sub is not None

    time_str = format_time_remaining(hw.deadline)
    deadline_str = hw.deadline.strftime("%Y-%m-%d %H:%M")

    if hw.status == "pending":
        status_emoji = "⏳"
        status_text = "Not started"
    elif hw.status == "submitted":
        status_emoji = "📤"
        status_text = "Submitted, awaiting review"
    else:
        status_emoji = "✅"
        status_text = "Reviewed"

    text = (
        f"📝 <b>Homework #{hw.id}</b>\n\n"
        f"{hw.task}\n\n"
        f"{time_str}\n"
        f"Due: <code>{deadline_str}</code>\n"
        f"Status: {status_emoji} {status_text}"
    )

    if latest_sub is not None:
        submitted_str = latest_sub.submitted_at.strftime("%Y-%m-%d %H:%M")
        late_tag = " ⚠️ late" if latest_sub.is_late else ""
        text += (
            f"\n\n<b>Your last submission</b>\n"
            f"Sent: {submitted_str}{late_tag}"
        )
        if latest_sub.teacher_feedback:
            text += f"\n\n<b>Teacher feedback:</b>\n<i>{latest_sub.teacher_feedback}</i>"

    await callback.message.edit_text(
        text,
        reply_markup=homework_detail_keyboard(
            homework_id=homework_id,
            already_submitted=already_submitted,
            is_reviewed=(hw.status == "reviewed"),
        ),
        parse_mode="HTML",
    )
    await callback.answer()


# ---------- Submission flow ----------

@router.callback_query(F.data.startswith("hw:submit:"))
async def cb_hw_submit(callback: CallbackQuery, state: FSMContext, bot: Bot):
    student = await _require_active_student_cb(callback)
    if student is None:
        return

    homework_id = int(callback.data.split(":")[2])
    hw = await get_homework(homework_id)
    if hw is None:
        await callback.answer("Homework not found.", show_alert=True)
        return

    if hw.student_id != callback.from_user.id:
        await callback.answer("Not your homework.", show_alert=True)
        return

    # Delete the detail view — student doesn't need it duplicated
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Initialize the submission batch in FSM state
    await state.update_data(
        submit_homework_id=homework_id,
        submit_items=[],
    )

    await _start_collecting(callback.message, state, hw, first_time=True)
    await callback.answer()



# ---------- Collecting items -------------------------------------------------------------

@router.message(SubmitHomework.collecting, F.text)
async def collect_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.startswith("/"):
        await message.answer("Please send your answer, not a command. Use /cancel to stop.")
        return
    if len(text) < 2:
        await message.answer("That seems too short.")
        return

    await _add_item(
        message=message,
        state=state,
        item={"type": "text", "content": text, "caption": None},
    )


@router.message(SubmitHomework.collecting, F.voice)
async def collect_voice(message: Message, state: FSMContext):
    await _add_item(
        message=message,
        state=state,
        item={
            "type": "voice",
            "content": message.voice.file_id,
            "caption": message.caption,
        },
    )


@router.message(SubmitHomework.collecting, F.photo)
async def collect_photo(message: Message, state: FSMContext):
    await _add_item(
        message=message,
        state=state,
        item={
            "type": "photo",
            "content": message.photo[-1].file_id,
            "caption": message.caption,
        },
    )


@router.message(SubmitHomework.collecting)
async def collect_wrong_type(message: Message):
    await message.answer(
        "Please send text, a voice message, or a photo. Use /cancel to stop."
    )


async def _add_item(
    message: Message,
    state: FSMContext,
    item: dict,
) -> None:
    """Append a new item to the batch and show the updated preview."""
    data = await state.get_data()
    items: list[dict] = data.get("submit_items", [])
    homework_id = data.get("submit_homework_id")

    if homework_id is None:
        await message.answer("Something went wrong. Please tap Submit again.")
        await state.clear()
        return

    hw = await get_homework(homework_id)
    if hw is None:
        await message.answer("Homework not found. Please try again.")
        await state.clear()
        return

    items.append(item)
    await state.update_data(submit_items=items)

    # Delete the previous preview message if we have one
    prev_preview_id = data.get("submit_preview_msg_id")
    if prev_preview_id:
        await _safe_delete_message(message.bot, message.chat.id, prev_preview_id)

    # Send a fresh preview
    from keyboards.inline import submission_preview_keyboard
    preview_msg = await message.answer(
        _build_preview_text(hw.task, items),
        reply_markup=submission_preview_keyboard(),
        parse_mode="HTML",
    )
    await state.update_data(submit_preview_msg_id=preview_msg.message_id)



    # Student confirmation
    late_note = "\n⚠️ Submitted after the deadline." if submission.is_late else ""
    resub_note = f"\n(This is submission #{submission_number})" if is_resubmission else ""
    await message.answer(
        f"✅ <b>Submission received</b>\n\n"
        f"Homework #{homework_id}{late_note}{resub_note}\n"
        "Your teacher will review it soon.",
        parse_mode="HTML",
    )

    # Look up student name for the admin notification
    student = await get_student(message.from_user.id)
    student_name = student.full_name if student else "Unknown"

    type_emoji = {"text": "📝", "voice": "🎙", "photo": "🖼"}[content_type]
    late_tag = " ⚠️ LATE" if submission.is_late else ""

    # Notify the teacher with a clean card
    if is_resubmission:
        headline = f"🔄 <b>Resubmission #{submission_number}</b>{late_tag}"
    else:
        headline = f"📬 <b>New submission</b>{late_tag}"

    notification = (
        f"{headline}\n\n"
        f"Student: <b>{escape(student_name)}</b>\n"
        f"Homework: #{homework_id}"
    )
    from keyboards.inline import submission_notification_keyboard
    try:
        await bot.send_message(
            ADMIN_ID,
            notification,
            reply_markup=submission_notification_keyboard(homework_id),
            parse_mode="HTML",
        )
    except Exception as e:
        import logging
        logging.warning(f"Failed to notify admin of submission: {e}")


# ---------- Submission flow callbacks ----------

@router.callback_query(F.data == "submit:cancel")
async def cb_submit_cancel(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.clear()
    await callback.message.answer("Submission cancelled.")
    await callback.answer()


@router.callback_query(F.data == "submit:edit")
async def cb_submit_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    items: list[dict] = data.get("submit_items", [])
    if not items:
        await callback.answer("Nothing to edit.", show_alert=True)
        return

    items_for_kb = [
        {"index": i + 1, "label": _format_item_label(item, i + 1)}
        for i, item in enumerate(items)
    ]

    lines = ["✏️ <b>Edit items</b>", ""]
    for i, item in enumerate(items, start=1):
        lines.append(f"{i}. {_format_item_label(item, i)}")
    lines.append("")
    lines.append("Tap an item to remove it, or add more.")
    text = "\n".join(lines)

    from keyboards.inline import submission_edit_keyboard
    await callback.message.edit_text(
        text,
        reply_markup=submission_edit_keyboard(items_for_kb),
        parse_mode="HTML",
    )
    await callback.answer()
    await state.set_state(SubmitHomework.editing)


@router.callback_query(SubmitHomework.editing, F.data.startswith("submit:remove:"))
async def cb_submit_remove(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[2])
    data = await state.get_data()
    items: list[dict] = data.get("submit_items", [])

    if index < 0 or index >= len(items):
        await callback.answer("Item not found.", show_alert=True)
        return

    removed = items.pop(index)
    await state.update_data(submit_items=items)

    # Re-render the edit view (or go back to preview if empty)
    if not items:
        await callback.answer(f"Removed. No items left.")
        homework_id = data.get("submit_homework_id")
        hw = await get_homework(homework_id) if homework_id else None
        if hw is None:
            await state.clear()
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer("Submission cancelled.")
            return
        # Go back to collecting
        try:
            await callback.message.delete()
        except Exception:
            pass
        await _start_collecting(callback.message, state, hw, first_time=False)
        return

    # Re-render the edit view
    items_for_kb = [
        {"index": i + 1, "label": _format_item_label(item, i + 1)}
        for i, item in enumerate(items)
    ]
    lines = ["✏️ <b>Edit items</b>", ""]
    for i, item in enumerate(items, start=1):
        lines.append(f"{i}. {_format_item_label(item, i)}")
    lines.append("")
    lines.append("Tap an item to remove it, or add more.")
    text = "\n".join(lines)

    from keyboards.inline import submission_edit_keyboard
    await callback.message.edit_text(
        text,
        reply_markup=submission_edit_keyboard(items_for_kb),
        parse_mode="HTML",
    )
    await callback.answer("Removed.")


@router.callback_query(F.data == "submit:addmore")
async def cb_submit_addmore(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    homework_id = data.get("submit_homework_id")
    hw = await get_homework(homework_id) if homework_id else None
    if hw is None:
        await callback.answer("Something went wrong.", show_alert=True)
        await state.clear()
        return

    try:
        await callback.message.delete()
    except Exception:
        pass

    # Reset preview msg id since we just deleted the current screen
    await state.update_data(submit_preview_msg_id=None)

    await _start_collecting(callback.message, state, hw, first_time=False)
    await callback.answer()


@router.callback_query(F.data == "submit:back")
async def cb_submit_back(callback: CallbackQuery, state: FSMContext):
    """Back from edit view to the preview."""
    data = await state.get_data()
    items: list[dict] = data.get("submit_items", [])
    homework_id = data.get("submit_homework_id")
    hw = await get_homework(homework_id) if homework_id else None
    if hw is None or not items:
        await callback.answer("Nothing to show.", show_alert=True)
        return

    from keyboards.inline import submission_preview_keyboard
    await callback.message.edit_text(
        _build_preview_text(hw.task, items),
        reply_markup=submission_preview_keyboard(),
        parse_mode="HTML",
    )
    await state.update_data(submit_preview_msg_id=callback.message.message_id)
    await state.set_state(SubmitHomework.collecting)
    await callback.answer()


@router.callback_query(F.data == "submit:done")
async def cb_submit_done(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Finalize the batch — write all items to the DB and notify admin."""
    data = await state.get_data()
    items: list[dict] = data.get("submit_items", [])
    homework_id = data.get("submit_homework_id")

    if not items or homework_id is None:
        await callback.answer("Nothing to submit.", show_alert=True)
        return

    import uuid
    batch_id = str(uuid.uuid4())

    # Write all items under the same batch_id
    batch_number = None
    is_late = False
    for item in items:
        result = await add_submission(
            homework_id=homework_id,
            batch_id=batch_id,
            content_type=item["type"],
            content=item["content"],
            caption=item.get("caption"),
        )
        if result is None:
            await callback.answer("Homework not found.", show_alert=True)
            await state.clear()
            return
        submission, batch_number = result
        if submission.is_late:
            is_late = True

    is_resubmission = (batch_number or 1) > 1

    # Delete the preview message — flow is done
    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.clear()

    late_note = "\n⚠️ Submitted after the deadline." if is_late else ""
    resub_note = f"\n(This is submission #{batch_number})" if is_resubmission else ""
    await callback.message.answer(
        f"✅ <b>Submission received</b>\n\n"
        f"Homework #{homework_id}\n"
        f"{len(items)} item{'s' if len(items) != 1 else ''}{late_note}{resub_note}\n"
        "Your teacher will review it soon.",
        parse_mode="HTML",
    )
    await callback.answer("Submitted!")

    # Notify the teacher
    student = await get_student(callback.from_user.id)
    student_name = student.full_name if student else "Unknown"

    if is_resubmission:
        headline = f"🔄 <b>Resubmission #{batch_number}</b>"
    else:
        headline = "📬 <b>New submission</b>"
    if is_late:
        headline += " ⚠️ LATE"

    notification = (
        f"{headline}\n\n"
        f"Student: <b>{escape(student_name)}</b>\n"
        f"Homework: #{homework_id}\n"
        f"Items: {len(items)}"
    )
    from keyboards.inline import submission_notification_keyboard
    try:
        await bot.send_message(
            ADMIN_ID,
            notification,
            reply_markup=submission_notification_keyboard(homework_id),
            parse_mode="HTML",
        )
    except Exception as e:
        import logging
        logging.warning(f"Failed to notify admin of submission: {e}")