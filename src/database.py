import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect, text
import os

# Database setup
db_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'planner.db')
print(f"Using database file: {db_file}")
engine = create_engine(f'sqlite:///{db_file}', echo=False, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# import models so they are registered with Base
import models

# create tables for any missing models
Base.metadata.create_all(bind=engine)

# CalendarEvent migration disabled to preserve existing events

# auto-add 'section' column if missing
insp = inspect(engine)
if 'class_subject' in insp.get_table_names():
    cols = [c['name'] for c in insp.get_columns('class_subject')]
    if 'section' not in cols:
        # use SQLAlchemy 2.0 execution for DDL
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE class_subject ADD COLUMN section TEXT"))
    if 'start_date' not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE class_subject ADD COLUMN start_date DATE"))

# auto-add 'all_shared_roster' column if missing
if 'school_config' in insp.get_table_names():
    cols = [c['name'] for c in insp.get_columns('school_config')]
    if 'all_shared_roster' not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE school_config ADD COLUMN all_shared_roster BOOLEAN NOT NULL DEFAULT 0"))

# auto-add 'lesson_type' and 'status' columns if missing
if 'lesson' in insp.get_table_names():
    cols = [c['name'] for c in insp.get_columns('lesson')]
    if 'lesson_type' not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE lesson ADD COLUMN lesson_type TEXT"))
    if 'status' not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE lesson ADD COLUMN status TEXT"))
    # auto-add 'review_status' and 'anchor_date' columns if missing
    if 'review_status' not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE lesson ADD COLUMN review_status TEXT"))
    if 'anchor_date' not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE lesson ADD COLUMN anchor_date DATE"))
    # auto-add 'sequence' column if missing
    if 'sequence' not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE lesson ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0"))