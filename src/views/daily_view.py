from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, QDateEdit, QGridLayout, QSizePolicy, QFrame, QCheckBox, QLineEdit, QMessageBox
from PyQt5.QtCore import Qt, QDate
from database import SessionLocal
from models import ClassSubject, Lesson, SchoolConfig, CalendarEvent, EventType, MaterialNeeded
from .weekly_view import ClickableFrame
from .lesson_detail_dialog import LessonDetailDialog
from datetime import timedelta, date
import os

class DailyView(QWidget):
    def __init__(self):
        super().__init__()
        self.session = SessionLocal()
        self.current_date = QDate.currentDate()
        # navigation
        self.prev_button = QPushButton("Previous Day")
        self.next_button = QPushButton("Next Day")
        self.prev_button.setMaximumWidth(300)
        self.next_button.setMaximumWidth(300)
        # date selector
        self.date_edit = QDateEdit(calendarPopup=True)
        self.date_edit.setDate(self.current_date)
        self.date_edit.dateChanged.connect(self.on_date_changed)
        self.prev_button.clicked.connect(self.show_prev_day)
        self.next_button.clicked.connect(self.show_next_day)
        nav = QHBoxLayout()
        nav.addWidget(self.prev_button)
        nav.addWidget(self.next_button)
        nav.addWidget(self.date_edit)
        # search bar for lessons
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search lesson...")
        self.search_input.setMaximumWidth(300)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_lesson)
        nav.addWidget(self.search_input)
        nav.addWidget(self.search_button)
        # scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.scroll.setWidget(self.content)
        self.content_layout = QVBoxLayout(self.content)
        # main layout
        main = QVBoxLayout(self)
        main.addLayout(nav)
        main.addWidget(self.scroll)
        self.setLayout(main)
        # init view
        self.update_date_label()
        self.refresh_view()

    def update_date_label(self):
        self.date_edit.setDate(self.current_date)

    def show_prev_day(self):
        self.current_date = self.current_date.addDays(-1)
        self.update_date_label()
        self.refresh_view()

    def show_next_day(self):
        self.current_date = self.current_date.addDays(1)
        self.update_date_label()
        self.refresh_view()

    def show_detail(self, lesson_id):
        dlg = LessonDetailDialog(self, lesson_id)
        dlg.exec_()
        self.refresh_view()

    def refresh_view(self):
        # clear old
        for i in reversed(range(self.content_layout.count())):
            w = self.content_layout.takeAt(i).widget()
            if w: w.deleteLater()
        # fetch sections
        sections = self.session.query(ClassSubject).order_by(ClassSubject.section).all()
        config = self.session.query(SchoolConfig).first()
        # schedule map
        self.schedule_map = {}
        for subj in sections:
            lessons_all = self.session.query(Lesson).filter_by(class_subject_id=subj.id).order_by(Lesson.sequence).all()
            start_event = self.session.query(CalendarEvent).filter(CalendarEvent.event_type == subj.name).order_by(CalendarEvent.date).first()
            if start_event:
                base_date = start_event.date
            elif subj.start_date:
                base_date = subj.start_date
            elif config and config.start_date:
                base_date = config.start_date
            else:
                base_date = date.today()
            d = base_date
            for les in lessons_all:
                if les.anchor_date:
                    scheduled = les.anchor_date
                    d = scheduled
                else:
                    while d.weekday() >= 5:
                        d += timedelta(days=1)
                    scheduled = d
                self.schedule_map.setdefault((subj.id, scheduled), []).append(les)
                d = scheduled + timedelta(days=1)
        # colors
        color_map = {}
        for subj in sections:
            et = self.session.query(EventType).filter_by(name=subj.name).first()
            color_map[subj.id] = et.color if et else "#FFFFFF"
        # build cards
        for subj in sections:
            dt = self.current_date.toPyDate()
            lessons = self.schedule_map.get((subj.id, dt), [])
            card = ClickableFrame()
            card.setFrameShape(QFrame.StyledPanel)
            color = color_map.get(subj.id, "#FFFFFF")
            card.setStyleSheet(f"background-color: {color}; border:1px solid #444; border-radius:8px; padding:4px;")
            # grid layout for header and first-lesson data
            grid = QGridLayout(card)
            grid.setContentsMargins(2,2,2,2)
            headers = ["Lesson Number","Lesson Name","Objective","Plans","Post Notes","Materials","Attachments"]
            for col, txt in enumerate(headers):
                hdr = QLabel(txt)
                hdr.setStyleSheet("font-weight:bold; text-decoration: underline;")
                hdr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                hdr.setMinimumWidth(0)
                grid.addWidget(hdr, 0, col)
                grid.setColumnStretch(col, 1)
            if lessons:
                les = lessons[0]
                values = [
                    elide(les.number,10),
                    elide(les.name,20),
                    les.learning_objective or "",
                    les.lesson_plans_notes or "",
                    les.post_lesson_notes or ""
                ]
                for col, val in enumerate(values):
                    lbl = QLabel(val)
                    lbl.setWordWrap(True)
                    lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    lbl.setMinimumWidth(0)
                    grid.addWidget(lbl, 1, col)
                card.clicked.connect(lambda lid=les.id: self.show_detail(lid))
                # materials with checkboxes
                mat_widget = QWidget()
                mat_layout = QVBoxLayout(mat_widget)
                for m in self.session.query(MaterialNeeded).filter_by(lesson_id=les.id).all():
                    cb = QCheckBox(m.description)
                    cb.setChecked(m.acquired)
                    if m.acquired:
                        cb.setStyleSheet("text-decoration: line-through; color: gray;")
                    cb.stateChanged.connect(lambda state, _m=m, _cb=cb: self._daily_toggle_material(_m, _cb, state))
                    mat_layout.addWidget(cb)
                grid.addWidget(mat_widget, 1, 5)
                # attachments as links in final column
                attachments = (les.pdf_paths or "").split(",")
                html = ""
                for p in attachments:
                    if p:
                        name = os.path.basename(p)
                        href = p if p.startswith(("http://","https://")) else "file://" + p
                        html += f"<a href='{href}'>{name}</a><br/>"
                lbl = QLabel(html)
                lbl.setTextFormat(Qt.RichText)
                lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
                lbl.setOpenExternalLinks(True)
                lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                lbl.setMinimumWidth(0)
                grid.addWidget(lbl, 1, 6)
            else:
                lbl_empty = QLabel("No lesson")
                lbl_empty.setAlignment(Qt.AlignCenter)
                lbl_empty.setStyleSheet("color: gray;")
                lbl_empty.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                lbl_empty.setMinimumWidth(0)
                grid.addWidget(lbl_empty, 1, 0, 1, len(headers))
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0,4,0,4)
            subject_label = QLabel(subj.name)
            subject_label.setFixedWidth(80)
            subject_label.setStyleSheet("font-weight:bold;")
            row_layout.addWidget(subject_label)
            row_layout.addWidget(card)
            row_layout.setStretch(0, 1)
            row_layout.setStretch(1, 9)
            self.content_layout.addWidget(row)

    def on_date_changed(self, qdate):
        self.current_date = qdate
        self.refresh_view()

    def _daily_toggle_material(self, m, cb, state):
        m.acquired = (state == Qt.Checked)
        self.session.commit()
        if m.acquired:
            cb.setStyleSheet("text-decoration: line-through; color: gray;")
        else:
            cb.setStyleSheet("")

    def search_lesson(self):
        text = self.search_input.text().strip()
        if not text:
            return
        lesson = self.session.query(Lesson).filter(Lesson.name.ilike(f"%{text}%")).first()
        if not lesson:
            QMessageBox.information(self, "Not found", f"No lesson matching '{text}'")
            return
        # refresh to ensure schedule_map is current
        self.refresh_view()
        for (subj_id, dt), lessons in self.schedule_map.items():
            if any(l.id == lesson.id for l in lessons):
                self.current_date = QDate(dt.year, dt.month, dt.day)
                self.date_edit.setDate(self.current_date)
                self.refresh_view()
                return
        QMessageBox.information(self, "Not scheduled", "Lesson not found in current schedule")

def elide(text, length=30):
    return text if text and len(text)<=length else (text[:length]+"…") if text else ""
