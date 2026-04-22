from aiogram.filters import BaseFilter
from aiogram.types import Message

from config import ADMIN_ID


class IsAdmin(BaseFilter):
    """Passes only if the message is from the configured admin."""

    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id == ADMIN_ID


class IsNotAdmin(BaseFilter):
    """Passes only if the message is NOT from the admin.

    Used on the student router so admin messages don't leak into student handlers.
    """

    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id != ADMIN_ID