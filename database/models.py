from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Student(Base):
    __tablename__ = "students"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(128))
    level: Mapped[str | None] = mapped_column(String(2), nullable=True)

    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Student {self.telegram_id} {self.full_name!r}>"

class Homework(Base):
    __tablename__ = "homeworks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Which student this homework is for
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("students.telegram_id", ondelete="CASCADE")
    )

    # The assignment text (what you tell the student to do)
    task: Mapped[str] = mapped_column(Text)

    # When it's due (teacher-local time)
    deadline: Mapped[datetime] = mapped_column(DateTime)

    # Status: pending (no submission yet), submitted (student has submitted
    # at least once), reviewed (teacher has marked it reviewed)
    status: Mapped[str] = mapped_column(String(16), default="pending")

    # When this homework was assigned
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationship to submissions (one homework, many submissions)
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="homework",
        cascade="all, delete-orphan",
        order_by="Submission.submitted_at",
    )

    def __repr__(self) -> str:
        return f"<Homework #{self.id} student={self.student_id} status={self.status}>"


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    homework_id: Mapped[int] = mapped_column(
        ForeignKey("homeworks.id", ondelete="CASCADE")
    )

    # Items from one "submit session" share a batch_id.
    # Multiple items (photo + voice + text) can be grouped as one submission.
    batch_id: Mapped[str] = mapped_column(String(36))

    content_type: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    is_late: Mapped[bool] = mapped_column(Boolean, default=False)

    teacher_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    homework: Mapped["Homework"] = relationship(back_populates="submissions")

    def __repr__(self) -> str:
        return f"<Submission #{self.id} homework={self.homework_id} batch={self.batch_id[:8]} type={self.content_type}>"