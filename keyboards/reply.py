from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


# Admin button labels
BTN_STUDENTS = "👥 Students"
BTN_BLOCKED = "🚫 Blocked"
BTN_ASSIGN_HW = "📝 Assign homework"
BTN_COMMANDS = "❓ Commands"
BTN_TO_REVIEW = "🔔 To review"

# Student button labels
BTN_HOMEWORK = "📚 Homework"
BTN_VOCAB = "📖 Vocab"
BTN_PROGRESS = "📊 Progress"
BTN_PROFILE = "👤 Profile"
BTN_REPORT = "📨 Report an issue"


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_STUDENTS), KeyboardButton(text=BTN_ASSIGN_HW)],
            [KeyboardButton(text=BTN_TO_REVIEW), KeyboardButton(text=BTN_BLOCKED)],
            [KeyboardButton(text=BTN_COMMANDS)],
        ],
        resize_keyboard=True,
    )


def student_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_HOMEWORK), KeyboardButton(text=BTN_VOCAB)],
            [KeyboardButton(text=BTN_PROGRESS), KeyboardButton(text=BTN_PROFILE)],
            [KeyboardButton(text=BTN_REPORT)],
        ],
        resize_keyboard=True,
    )


def remove_menu() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()

