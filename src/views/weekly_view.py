from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QTableWidget, QFrame, QGridLayout, QSizePolicy, QDateEdit, QCheckBox, QLineEdit, QMessageBox, QHeaderView
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from database import SessionLocal
from models import ClassSubject, Lesson, SchoolConfig, CalendarEvent, EventType, MaterialNeeded
from .lesson_detail_dialog import LessonDetailDialog
from datetime import timedelta, date
import os

class ClickableFrame(QFrame):
    clicked = pyqtSignal()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

class WeeklyView(QWidget):
    def __init__(self):
        super().__init__()
        self.session = SessionLocal()
        # subject chooser
        self.subj_combo = QComboBox()
        names = [r[0] for r in self.session.query(ClassSubject.name).distinct().all()]
        for name in names:
            self.subj_combo.addItem(name)
        self.subj_combo.currentIndexChanged.connect(self.refresh_view)
        # week navigation
        self.current_date = QDate.currentDate()
        self.prev_button = QPushButton("Previous Week")
        self.next_button = QPushButton("Next Week")
        self.prev_button.setMaximumWidth(300)
        self.next_button.setMaximumWidth(300)
        self.week_label = QLabel()
        self.week_label.setAlignment(Qt.AlignCenter)
        self.prev_button.clicked.connect(self.show_prev_week)
        self.next_button.clicked.connect(self.show_next_week)
        # week date selector
        self.week_date_edit = QDateEdit(calendarPopup=True)
        self.week_date_edit.setDate(self.current_date)
        self.week_date_edit.dateChanged.connect(self.on_week_date_changed)
        # layout nav
        nav = QHBoxLayout()
        nav.addWidget(self.subj_combo)
        nav.addWidget(self.prev_button)
        nav.addWidget(self.next_button)
        nav.addWidget(self.week_label)
        nav.addWidget(self.week_date_edit)
        # search bar for lessons
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search lesson...")
        self.search_input.setMaximumWidth(300)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_lesson)
        nav.addWidget(self.search_input)
        nav.addWidget(self.search_button)
        # table
        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        # main layout
        main = QVBoxLayout(self)
        main.addLayout(nav)
        main.addWidget(self.table)
        self.setLayout(main)
        # init
        self.update_week_label()
        self.refresh_view()

    def update_week_label(self):
        dow = self.current_date.dayOfWeek()
        monday = self.current_date.addDays(-(dow-1))
        friday = monday.addDays(4)
        self.monday = monday
        # school-year week number
        name = self.subj_combo.currentText()
        cs = self.session.query(ClassSubject).filter_by(name=name).first()
        config = self.session.query(SchoolConfig).first()
        base_date = cs.start_date if cs and cs.start_date else (config.start_date if config and config.start_date else None)
        if base_date:
            diff = (monday.toPyDate() - base_date).days
            week_num = diff // 7 + 1 if diff >= 0 else 1
        else:
            week_num = monday.weekNumber()[0]
        self.week_label.setText(f"Week {week_num}: {monday.toString('MMM d')} - {friday.toString('MMM d')}")

    def show_prev_week(self):
        self.current_date = self.current_date.addDays(-7)
        self.update_week_label()
        self.refresh_view()

    def show_next_week(self):
        self.current_date = self.current_date.addDays(7)
        self.update_week_label()
        self.refresh_view()

    def show_detail(self, lesson_id):
        dlg = LessonDetailDialog(self, lesson_id)
        dlg.exec_()
        self.refresh_view()

    def refresh_view(self):
        # clear table
        name = self.subj_combo.currentText()
        sections = self.session.query(ClassSubject).filter_by(name=name).order_by(ClassSubject.section).all()
        days = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
        # fetch class colors for card backgrounds
        color_map = {}
        for subj in sections:
            et = self.session.query(EventType).filter_by(name=subj.name).first()
            color_map[subj.id] = et.color if et else "#FFFFFF"
        # compute schedule map for all lessons (anchor_date or sequential)
        config = self.session.query(SchoolConfig).first()
        self.schedule_map = {}
        for subj in sections:
            # get all lessons in defined sequence
            lessons_all = self.session.query(Lesson).filter_by(class_subject_id=subj.id).order_by(Lesson.sequence).all()
            # determine base start date via CalendarEvent, class start_date, or global start_date
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
        self.table.clear()
        self.table.setRowCount(len(days))
        self.table.setColumnCount(len(sections))
        self.table.setHorizontalHeaderLabels([subj.section or "" for subj in sections])
        self.table.setVerticalHeaderLabels(days)
        for i, day in enumerate(days):
            dt = self.monday.addDays(i).toPyDate()
            for j, subj in enumerate(sections):
                lessons = self.schedule_map.get((subj.id, dt), [])
                cell_widget = QWidget()
                layout = QVBoxLayout(cell_widget)
                layout.setContentsMargins(2,2,2,2)
                if not lessons:
                    card = ClickableFrame()
                    card.setFrameShape(QFrame.StyledPanel)
                    card.setStyleSheet("background-color: #FFFFFF; border:1px solid #AAA; border-radius:8px; padding:4px;")
                    vcl_empty = QVBoxLayout(card)
                    lbl_empty = QLabel("No lesson")
                    lbl_empty.setAlignment(Qt.AlignCenter)
                    lbl_empty.setStyleSheet("color: gray;")
                    vcl_empty.addWidget(lbl_empty)
                    layout.addWidget(card)
                else:
                    for les in lessons:
                        card = ClickableFrame()
                        card.clicked.connect(lambda lid=les.id: self.show_detail(lid))
                        card.setFrameShape(QFrame.StyledPanel)
                        color = color_map.get(subj.id, "#FFFFFF")
                        card.setStyleSheet(f"background-color: {color}; border:1px solid #444; border-radius:8px; padding:4px;")
                        grid = QGridLayout(card)
                        grid.setContentsMargins(2,2,2,2)
                        headers = ["Lesson Number","Lesson Name","Objective","Plans","Post Notes","Materials","PDFs"]
                        for col, txt in enumerate(headers):
                            hdr = QLabel(txt)
                            hdr.setStyleSheet("font-weight:bold; text-decoration: underline;")
                            hdr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                            hdr.setMinimumWidth(0)
                            grid.addWidget(hdr, 0, col)
                            grid.setColumnStretch(col, 1)
                        # populate all but attachments column
                        values = [
                            elide(les.number,10),
                            elide(les.name,20),
                            les.learning_objective or "",
                            les.lesson_plans_notes or "",
                            les.post_lesson_notes or "",
                        ]
                        for col, val in enumerate(values):
                            lbl = QLabel(val)
                            lbl.setWordWrap(True)
                            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                            lbl.setMinimumWidth(0)
                            grid.addWidget(lbl, 1, col)
                        # materials with checkboxes
                        mat_widget = QWidget()
                        mat_layout = QVBoxLayout(mat_widget)
                        for m in self.session.query(MaterialNeeded).filter_by(lesson_id=les.id).all():
                            cb = QCheckBox(m.description)
                            cb.setChecked(m.acquired)
                            if m.acquired:
                                cb.setStyleSheet("text-decoration: line-through; color: gray;")
                            cb.stateChanged.connect(lambda state, _m=m, _cb=cb: self._weekly_toggle_material(_m, _cb, state))
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
                        grid.addWidget(lbl, 1, len(headers)-1)
                        layout.addWidget(card)
                self.table.setCellWidget(i, j, cell_widget)
        self.table.resizeRowsToContents()

    def on_week_date_changed(self, qdate):
        self.current_date = qdate
        self.update_week_label()
        self.refresh_view()

    def _weekly_toggle_material(self, m, cb, state):
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
        session = SessionLocal()
        lesson = session.query(Lesson).filter(Lesson.name.ilike(f"%{text}%")).first()
        session.close()
        if not lesson:
            QMessageBox.information(self, "Not found", f"No lesson matching '{text}'")
            return
        # rebuild schedule_map for full range
        self.refresh_view()
        for (subj_id, dt), lessons in self.schedule_map.items():
            if any(l.id == lesson.id for l in lessons):
                qdate = QDate(dt.year, dt.month, dt.day)
                self.current_date = qdate
                self.week_date_edit.setDate(qdate)
                self.update_week_label()
                self.refresh_view()
                return
        QMessageBox.information(self, "Not scheduled", "Lesson not found in current schedule")

def elide(text, length=30): return text if text and len(text)<=length else (text[:length]+"…") if text else ""
