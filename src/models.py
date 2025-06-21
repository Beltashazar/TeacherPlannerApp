import datetime
from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, Text
from database import Base

class SchoolConfig(Base):
    __tablename__ = "school_config"
    id = Column(Integer, primary_key=True, index=True)
    school_name = Column(String, nullable=False, default="")
    teacher_name = Column(String, nullable=False, default="")
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    logo_path = Column(String, nullable=True)
    all_shared_roster = Column(Boolean, nullable=False, default=False)

class ClassSubject(Base):
    __tablename__ = "class_subject"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    section = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)

class EventType(Base):
    __tablename__ = "event_type"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String, nullable=False)

class CalendarEvent(Base):
    __tablename__ = "calendar_event"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    event_type = Column(String, nullable=False)

# Scope & Sequence lessons per class
class Lesson(Base):
    __tablename__ = "lesson"
    id = Column(Integer, primary_key=True, index=True)
    class_subject_id = Column(Integer, ForeignKey("class_subject.id"), nullable=False)
    number = Column(String, nullable=False)
    name = Column(String, nullable=True)
    learning_objective = Column(Text, nullable=True)
    lesson_type = Column(String, nullable=True)
    status = Column(String, nullable=True)
    review_status = Column(String, nullable=True)  # 'Pending' or 'Approved'
    anchor_date = Column(Date, nullable=True)      # optional anchored lesson date
    sequence = Column(Integer, nullable=False, default=0)  # lesson order
    lesson_plans_notes = Column(Text, nullable=True)
    post_lesson_notes = Column(Text, nullable=True)
    materials = Column(String, nullable=True)  # comma-separated
    pdf_paths = Column(String, nullable=True)  # comma-separated

# Performance entries per lesson for student performance
class LessonPerformance(Base):
    __tablename__ = "lesson_performance"
    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lesson.id"), nullable=False)
    roster_entry_id = Column(Integer, ForeignKey("roster_entry.id"), nullable=False)
    status = Column(String, nullable=True)  # e.g. "Green", "Yellow", "Red"
    notes = Column(Text, nullable=True)

# Roster entries for classes (null class_subject_id = global roster)
class RosterEntry(Base):
    __tablename__ = "roster_entry"
    id = Column(Integer, primary_key=True, index=True)
    class_subject_id = Column(Integer, ForeignKey("class_subject.id"), nullable=True)
    name = Column(String, nullable=False)

class MaterialNeeded(Base):
    __tablename__ = "material_needed"
    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lesson.id"), nullable=False)
    description = Column(String, nullable=False)
    reminder_date = Column(Date, nullable=False)
    acquired = Column(Boolean, nullable=False, default=False)