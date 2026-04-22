from aiogram.fsm.state import State, StatesGroup


class AssignHomework(StatesGroup):
    choosing_student = State()
    typing_task = State()
    choosing_deadline = State()
    typing_custom_date = State()
    confirming = State()

class SubmitHomework(StatesGroup):
    collecting = State()
    editing = State()

class ReviewHomework(StatesGroup):
    typing_feedback = State()
