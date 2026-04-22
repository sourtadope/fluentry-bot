from sqlalchemy import select

from database.db import async_session
from database.models import Student, Homework, Submission


async def get_student(telegram_id: int) -> Student | None:
    """Return the student with this telegram_id, or None if not found."""
    async with async_session() as session:
        result = await session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def create_student(
    telegram_id: int,
    full_name: str,
    username: str | None,
) -> Student:
    """Create a new (unapproved) student record."""
    async with async_session() as session:
        student = Student(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            is_approved=False,
            is_active=True,
            is_blocked=False,
        )
        session.add(student)
        await session.commit()
        return student

async def set_student_level(telegram_id: int, level: str) -> Student | None:
    """Update a student's CEFR level (A1–C2)."""
    async with async_session() as session:
        result = await session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()
        if student is None:
            return None
        student.level = level
        await session.commit()
        return student


async def approve_student(telegram_id: int) -> Student | None:
    async with async_session() as session:
        result = await session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()
        if student is None:
            return None
        student.is_approved = True
        await session.commit()
        return student


async def block_student(telegram_id: int) -> Student | None:
    """Mark a student as blocked. Other flags are left alone."""
    async with async_session() as session:
        result = await session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()
        if student is None:
            return None
        student.is_blocked = True
        await session.commit()
        return student


async def unblock_student(telegram_id: int) -> Student | None:
    """Unblock a user by deleting their record entirely.

    Next time they /start, they'll be treated as a fresh new user
    and a new approval request will go to the admin.

    Returns the deleted student (for display purposes), or None if not found.
    """
    async with async_session() as session:
        result = await session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()
        if student is None:
            return None
        # Detach a copy for the return value before deletion
        deleted_info = Student(
            telegram_id=student.telegram_id,
            full_name=student.full_name,
            username=student.username,
        )
        await session.delete(student)
        await session.commit()
        return deleted_info


async def archive_student(telegram_id: int) -> Student | None:
    """Soft-delete: mark as inactive. Data is preserved."""
    async with async_session() as session:
        result = await session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()
        if student is None:
            return None
        student.is_active = False
        await session.commit()
        return student


async def unarchive_student(telegram_id: int) -> Student | None:
    async with async_session() as session:
        result = await session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()
        if student is None:
            return None
        student.is_active = True
        await session.commit()
        return student


async def list_active_students() -> list[Student]:
    """Approved, active, non-blocked students."""
    async with async_session() as session:
        result = await session.execute(
            select(Student)
            .where(
                Student.is_approved == True,  # noqa: E712
                Student.is_active == True,    # noqa: E712
                Student.is_blocked == False,  # noqa: E712
            )
            .order_by(Student.full_name)
        )
        return list(result.scalars().all())


async def list_archived_students() -> list[Student]:
    async with async_session() as session:
        result = await session.execute(
            select(Student)
            .where(
                Student.is_active == False,  # noqa: E712
                Student.is_blocked == False, # noqa: E712
            )
            .order_by(Student.full_name)
        )
        return list(result.scalars().all())


async def list_blocked_students() -> list[Student]:
    async with async_session() as session:
        result = await session.execute(
            select(Student)
            .where(Student.is_blocked == True)  # noqa: E712
            .order_by(Student.full_name)
        )
        return list(result.scalars().all())


# =====================================================================
# Homework queries
# =====================================================================

from datetime import datetime
from database.models import Homework, Submission


async def create_homework(
    student_id: int,
    task: str,
    deadline: datetime,
) -> Homework:
    """Create a new homework assignment for a student."""
    async with async_session() as session:
        hw = Homework(
            student_id=student_id,
            task=task,
            deadline=deadline,
            status="pending",
        )
        session.add(hw)
        await session.commit()
        await session.refresh(hw)
        return hw


async def get_homework(homework_id: int) -> Homework | None:
    async with async_session() as session:
        result = await session.execute(
            select(Homework).where(Homework.id == homework_id)
        )
        return result.scalar_one_or_none()


async def list_student_homework_active(student_id: int) -> list[Homework]:
    """Pending and submitted (un-reviewed) homework, ordered by deadline."""
    async with async_session() as session:
        result = await session.execute(
            select(Homework)
            .where(
                Homework.student_id == student_id,
                Homework.status != "reviewed",
            )
            .order_by(Homework.deadline)
        )
        return list(result.scalars().all())


async def list_student_homework_reviewed(
    student_id: int,
    limit: int = 20,
) -> list[Homework]:
    """Reviewed homework, most recent first."""
    async with async_session() as session:
        result = await session.execute(
            select(Homework)
            .where(
                Homework.student_id == student_id,
                Homework.status == "reviewed",
            )
            .order_by(Homework.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

async def get_latest_batch_items(homework_id: int) -> list[Submission]:
    """Return all items of the most recent submission batch for a homework."""
    async with async_session() as session:
        # Find the batch_id of the most recent item
        latest_result = await session.execute(
            select(Submission)
            .where(Submission.homework_id == homework_id)
            .order_by(Submission.submitted_at.desc())
            .limit(1)
        )
        latest = latest_result.scalar_one_or_none()
        if latest is None:
            return []

        # Return all items sharing that batch_id
        batch_result = await session.execute(
            select(Submission)
            .where(
                Submission.homework_id == homework_id,
                Submission.batch_id == latest.batch_id,
            )
            .order_by(Submission.submitted_at)
        )
        return list(batch_result.scalars().all())


async def add_submission(
    homework_id: int,
    batch_id: str,
    content_type: str,
    content: str,
    caption: str | None = None,
) -> tuple[Submission, int] | None:
    """Add a submission item to a homework under the given batch.

    Returns (submission, batch_number) where batch_number is how many
    distinct batches this homework now has (1 for the first one, 2 for a
    resubmission batch, etc). Returns None if the homework doesn't exist.
    """
    async with async_session() as session:
        hw_result = await session.execute(
            select(Homework).where(Homework.id == homework_id)
        )
        hw = hw_result.scalar_one_or_none()
        if hw is None:
            return None

        # Count distinct batches for this homework (including the new one
        # if it's not already in there)
        from sqlalchemy import func, distinct
        batches_result = await session.execute(
            select(func.count(distinct(Submission.batch_id))).where(
                Submission.homework_id == homework_id
            )
        )
        existing_batch_count = batches_result.scalar_one() or 0

        # Check if this batch_id is new
        existing_result = await session.execute(
            select(Submission).where(
                Submission.homework_id == homework_id,
                Submission.batch_id == batch_id,
            ).limit(1)
        )
        is_new_batch = existing_result.scalar_one_or_none() is None
        batch_number = existing_batch_count + (1 if is_new_batch else 0)

        # Determine lateness
        now = datetime.now()
        deadline = hw.deadline
        if deadline.tzinfo is not None:
            deadline = deadline.replace(tzinfo=None)
        is_late = now > deadline

        sub = Submission(
            homework_id=homework_id,
            batch_id=batch_id,
            content_type=content_type,
            content=content,
            caption=caption,
            is_late=is_late,
        )
        session.add(sub)

        if hw.status == "pending":
            hw.status = "submitted"

        await session.commit()
        await session.refresh(sub)
        return sub, batch_number


async def get_latest_submission(homework_id: int) -> Submission | None:
    """Return the most recent submission for a homework, if any."""
    async with async_session() as session:
        result = await session.execute(
            select(Submission)
            .where(Submission.homework_id == homework_id)
            .order_by(Submission.submitted_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def mark_homework_reviewed(
    homework_id: int,
    feedback: str | None = None,
) -> Homework | None:
    """Mark a homework as reviewed. Attaches feedback to the latest submission."""
    async with async_session() as session:
        hw_result = await session.execute(
            select(Homework).where(Homework.id == homework_id)
        )
        hw = hw_result.scalar_one_or_none()
        if hw is None:
            return None

        hw.status = "reviewed"

        # Attach feedback to latest submission
        if feedback is not None:
            sub_result = await session.execute(
                select(Submission)
                .where(Submission.homework_id == homework_id)
                .order_by(Submission.submitted_at.desc())
                .limit(1)
            )
            sub = sub_result.scalar_one_or_none()
            if sub is not None:
                sub.teacher_feedback = feedback
                sub.reviewed_at = datetime.utcnow()

        await session.commit()
        return hw

async def student_homework_stats(student_id: int) -> dict:
    """Return a dict with counts: total, pending, submitted, reviewed."""
    async with async_session() as session:
        result = await session.execute(
            select(Homework).where(Homework.student_id == student_id)
        )
        homeworks = list(result.scalars().all())

    counts = {
        "total": len(homeworks),
        "pending": sum(1 for h in homeworks if h.status == "pending"),
        "submitted": sum(1 for h in homeworks if h.status == "submitted"),
        "reviewed": sum(1 for h in homeworks if h.status == "reviewed"),
    }
    return counts


async def list_submissions_to_review() -> list[tuple[Homework, Student, datetime]]:
    """Return all homeworks currently awaiting review.

    Returns a list of (homework, student, latest_submission_time) tuples,
    sorted by submission time (oldest waiting first).
    """
    async with async_session() as session:
        result = await session.execute(
            select(Homework).where(Homework.status == "submitted")
        )
        homeworks = list(result.scalars().all())

        output = []
        for hw in homeworks:
            # Get the latest submission time
            sub_result = await session.execute(
                select(Submission)
                .where(Submission.homework_id == hw.id)
                .order_by(Submission.submitted_at.desc())
                .limit(1)
            )
            latest_sub = sub_result.scalar_one_or_none()
            if latest_sub is None:
                continue  # shouldn't happen, but defensive

            # Load the student
            stu_result = await session.execute(
                select(Student).where(Student.telegram_id == hw.student_id)
            )
            student = stu_result.scalar_one_or_none()
            if student is None:
                continue  # orphaned homework, skip

            output.append((hw, student, latest_sub.submitted_at))

    output.sort(key=lambda t: t[2])  # oldest first
    return output


async def count_submissions_to_review() -> int:
    """Fast count of homeworks awaiting review, for menu badge display."""
    async with async_session() as session:
        from sqlalchemy import func
        result = await session.execute(
            select(func.count(Homework.id)).where(Homework.status == "submitted")
        )
        return result.scalar_one() or 0


async def get_oldest_pending_review_for_student(
    student_id: int,
    exclude_ids: set[int] | None = None,
) -> Homework | None:
    exclude_ids = exclude_ids or set()
    async with async_session() as session:
        result = await session.execute(
            select(Homework).where(
                Homework.student_id == student_id,
                Homework.status == "submitted",
            )
        )
        homeworks = [hw for hw in result.scalars().all() if hw.id not in exclude_ids]
        if not homeworks:
            return None

        oldest_hw = None
        oldest_time = None
        for hw in homeworks:
            sub_result = await session.execute(
                select(Submission)
                .where(Submission.homework_id == hw.id)
                .order_by(Submission.submitted_at.desc())
                .limit(1)
            )
            sub = sub_result.scalar_one_or_none()
            if sub is None:
                continue
            if oldest_time is None or sub.submitted_at < oldest_time:
                oldest_time = sub.submitted_at
                oldest_hw = hw

        return oldest_hw