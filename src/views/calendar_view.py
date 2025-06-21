from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QGroupBox, QSizePolicy, QHeaderView, QDialog, QLineEdit, QMessageBox
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QBrush
import calendar
from datetime import date, timedelta
from database import SessionLocal
from models import SchoolConfig, CalendarEvent, EventType, ClassSubject, Lesson
from .lesson_detail_dialog import LessonDetailDialog
from functools import partial

class CalendarView(QWidget):
    def __init__(self):
        super().__init__()

        # Main horizontal layout (left = summary & scope, right = calendar grid)
        main_layout = QHBoxLayout()

        # LEFT SIDE (Summary + Scope)
        left_layout = QVBoxLayout()
        # initialize and store summary section for dynamic refresh
        self.summary_box = self.create_summary_section()
        left_layout.addWidget(self.summary_box)
        left_container = QWidget()
        left_container.setLayout(left_layout)
        left_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        # RIGHT SIDE (Calendar Grid)
        right_layout = QVBoxLayout()
        self.create_calendar_grid(right_layout)
        right_container = QWidget()
        right_container.setLayout(right_layout)
        right_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Add both sides to main layout
        main_layout.addWidget(left_container)
        main_layout.addWidget(right_container)

        self.setLayout(main_layout)

    def create_summary_section(self):
        summary_box = QGroupBox("Yearly Dashboard")
        summary_layout = QVBoxLayout()
        session = SessionLocal()
        # show school start/end dates
        config = session.query(SchoolConfig).first()
        if config:
            start_lbl = QLabel(f"School Start: {config.start_date}")
            summary_layout.addWidget(start_lbl)
            end_lbl = QLabel(f"School End: {config.end_date}")
            summary_layout.addWidget(end_lbl)
        # Legend: count special events for full year
        today = date.today()
        ys, ye = date(today.year,1,1), date(today.year,12,31)
        for et in session.query(EventType).all():
            cnt = session.query(CalendarEvent).filter(CalendarEvent.event_type==et.name, CalendarEvent.date>=ys, CalendarEvent.date<=ye).count()
            if cnt == 0:
                continue
            lbl = QLabel(f"{et.name}: {cnt}")
            lbl.setStyleSheet(f"color: {et.color}")
            summary_layout.addWidget(lbl)
        # Class: lessons approved vs total (skip classes with no lessons)
        for cs in session.query(ClassSubject).all():
            total = session.query(Lesson).filter(Lesson.class_subject_id==cs.id).count()
            if total == 0:
                continue
            appr = session.query(Lesson).filter(Lesson.class_subject_id==cs.id, Lesson.review_status=="Approved").count()
            etc = session.query(EventType).filter_by(name=cs.name).first()
            clr = etc.color if etc else "#000000"
            lbl2 = QLabel(f"{cs.name}: {appr}/{total}")
            lbl2.setStyleSheet(f"color: {clr}")
            summary_layout.addWidget(lbl2)
        session.close()
        summary_box.setLayout(summary_layout)
        return summary_box

    def refresh_summary(self):
        # dynamically rebuild dashboard counts
        layout = self.summary_box.layout()
        # clear existing items
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        session = SessionLocal()
        config = session.query(SchoolConfig).first()
        # school start/end
        if config:
            start_lbl = QLabel(f"School Start: {config.start_date}")
            layout.addWidget(start_lbl)
            end_lbl = QLabel(f"School End: {config.end_date}")
            layout.addWidget(end_lbl)
        # Legend: count special events
        today = date.today()
        ys, ye = date(today.year,1,1), date(today.year,12,31)
        for et in session.query(EventType).all():
            cnt = session.query(CalendarEvent).filter(CalendarEvent.event_type==et.name, CalendarEvent.date>=ys, CalendarEvent.date<=ye).count()
            if cnt == 0:
                continue
            lbl = QLabel(f"{et.name}: {cnt}")
            lbl.setStyleSheet(f"color: {et.color}")
            layout.addWidget(lbl)
        # Class: approved vs total
        for cs in session.query(ClassSubject).all():
            total = session.query(Lesson).filter(Lesson.class_subject_id==cs.id).count()
            if total == 0:
                continue
            appr = session.query(Lesson).filter(Lesson.class_subject_id==cs.id, Lesson.review_status=="Approved").count()
            etc = session.query(EventType).filter_by(name=cs.name).first()
            clr = etc.color if etc else "#000000"
            lbl2 = QLabel(f"{cs.name}: {appr}/{total}")
            lbl2.setStyleSheet(f"color: {clr}")
            layout.addWidget(lbl2)
        session.close()

    def create_calendar_grid(self, parent_layout):
        # Month Navigation
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("Previous Month")
        self.next_button = QPushButton("Next Month")
        self.prev_button.setMaximumWidth(300)
        self.next_button.setMaximumWidth(300)
        self.month_label = QLabel()
        self.month_label.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)
        nav_layout.addWidget(self.month_label)
        # search bar for lessons
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search lesson...")
        self.search_input.setMaximumWidth(300)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_lesson)
        nav_layout.addWidget(self.search_input)
        nav_layout.addWidget(self.search_button)

        self.prev_button.clicked.connect(self.show_prev_month)
        self.next_button.clicked.connect(self.show_next_month)

        parent_layout.addLayout(nav_layout)

        # Calendar Grid
        self.calendar_table = QTableWidget(6, 7)
        # week from Sunday to Saturday
        self.calendar_table.setHorizontalHeaderLabels(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
        self.calendar_table.horizontalHeader().setStretchLastSection(True)
        self.calendar_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        parent_layout.addWidget(self.calendar_table)
        self.calendar_table.cellDoubleClicked.connect(self.handle_cell_double_click)
        self.current_date = QDate.currentDate()
        self.update_calendar()

    def update_calendar(self):
        self.calendar_table.clearContents()
        month_name = self.current_date.toString("MMMM yyyy")
        self.month_label.setText(month_name)
        year = self.current_date.year()
        month = self.current_date.month()
        _, num_days = calendar.monthrange(year, month)
        first_day = QDate(year, month, 1)
        # Sunday=0 ... Saturday=6
        start_column = first_day.dayOfWeek() % 7
        day = 1
        for row in range(6):
            for col in range(7):
                if (row == 0 and col < start_column) or day > num_days:
                    self.calendar_table.setItem(row, col, QTableWidgetItem(""))
                else:
                    item = QTableWidgetItem(str(day))
                    # shade weekends (Sun & Sat)
                    if col == 0 or col == 6:
                        item.setBackground(Qt.lightGray)
                    self.calendar_table.setItem(row, col, item)
                    day += 1

        # map days to table coords
        day_to_cell = {}
        for r in range(6):
            for c in range(7):
                it = self.calendar_table.item(r,c)
                if it and it.text().isdigit(): day_to_cell[int(it.text())]=(r,c)
        session = SessionLocal()
        # build class names list to skip start-event display
        class_names = [cs.name for cs in session.query(ClassSubject).all()]
        # paint special events
        special_events = session.query(CalendarEvent).filter(CalendarEvent.date>=date(year,month,1), CalendarEvent.date<=date(year,month,num_days)).all()
        for ev in special_events:
            # skip class start events
            if ev.event_type in class_names: continue
            cell = day_to_cell.get(ev.date.day)
            if cell:
                r,c = cell; it = self.calendar_table.item(r,c)
                e = session.query(EventType).filter_by(name=ev.event_type).first()
                if e: it.setBackground(QBrush(QColor(e.color)))
        # schedule and paint lessons
        self.schedule_map = {}
        # treat only non-class events as holidays for scheduling
        special_dates = {ev.date for ev in session.query(CalendarEvent).all() if ev.event_type not in class_names}
        for cs in session.query(ClassSubject).all():
            config = session.query(SchoolConfig).first()
            # determine base start date for class
            start_event = session.query(CalendarEvent)\
                .filter(CalendarEvent.event_type == cs.name)\
                .order_by(CalendarEvent.date).first()
            if start_event:
                start_date = start_event.date
            elif cs.start_date:
                start_date = cs.start_date
            elif config and config.start_date:
                start_date = config.start_date
            else:
                continue
            lessons = session.query(Lesson).filter_by(class_subject_id=cs.id).order_by(Lesson.sequence).all()
            d = start_date
            for l in lessons:
                # use anchor_date if provided
                if l.anchor_date:
                    scheduled = l.anchor_date
                    d = scheduled
                else:
                    # find next valid date
                    while d.weekday() >= 5 or d in special_dates:
                        d += timedelta(days=1)
                    scheduled = d
                # assign lesson to scheduled date
                self.schedule_map.setdefault(scheduled, []).append((l, cs))
                # advance for next lesson
                d = scheduled + timedelta(days=1)
        # render lessons: cell widget with day label + lesson buttons
        for d, entries in self.schedule_map.items():
            if d.year==year and d.month==month:
                pos = day_to_cell.get(d.day)
                if pos:
                    r,c = pos
                    # remove default day item to prevent duplicate label
                    self.calendar_table.takeItem(r, c)
                    w = QWidget()
                    vb = QVBoxLayout(w)
                    vb.setContentsMargins(2,2,2,2)
                    # Day label
                    day_lbl = QLabel(str(d.day))
                    vb.addWidget(day_lbl)
                    # Lesson entries each on its own line
                    for l, cs in entries:
                        # Text: ClassName - LessonNumber: LessonName
                        text = cs.name
                        if l.number:
                            text += f" - {l.number}"
                        if l.name:
                            text += f": {l.name}"
                        btn = QPushButton(text)
                        btn.setFlat(False)
                        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
                        ev = session.query(EventType).filter_by(name=cs.name).first()
                        col = QColor(ev.color if ev else "#000000")
                        col.setAlpha(255 if l.review_status=="Approved" else 128)
                        btn.setStyleSheet(
                            f"background-color: rgba({col.red()},{col.green()},{col.blue()},{col.alpha()}); "
                            "text-align: left; border-radius: 8px; padding: 4px;")
                        btn.clicked.connect(partial(self.open_lesson, l.id))
                        vb.addWidget(btn)
                    self.calendar_table.setCellWidget(r, c, w)
        session.close()
        # highlight school start/end dates
        cfg_session = SessionLocal()
        config = cfg_session.query(SchoolConfig).first()
        if config:
            sd = config.start_date
            if sd and sd.year==year and sd.month==month:
                pos0 = day_to_cell.get(sd.day)
                if pos0:
                    r0,c0 = pos0
                    et0 = cfg_session.query(EventType).filter_by(name="School Start").first()
                    scol = QColor(et0.color) if et0 else QColor("#00FF00")
                    w0 = self.calendar_table.cellWidget(r0,c0)
                    if w0:
                        w0.setStyleSheet(f"background-color: {scol.name()};")
                    else:
                        it0 = self.calendar_table.item(r0,c0)
                        if it0: it0.setBackground(QBrush(scol))
            ed = config.end_date
            if ed and ed.year==year and ed.month==month:
                pos1 = day_to_cell.get(ed.day)
                if pos1:
                    r1,c1 = pos1
                    et1 = cfg_session.query(EventType).filter_by(name="School End").first()
                    ecol = QColor(et1.color) if et1 else QColor("#FF0000")
                    w1 = self.calendar_table.cellWidget(r1,c1)
                    if w1:
                        w1.setStyleSheet(f"background-color: {ecol.name()};")
                    else:
                        it1 = self.calendar_table.item(r1,c1)
                        if it1: it1.setBackground(QBrush(ecol))
        cfg_session.close()
        # add vertical headers for week of school year
        session_hdr = SessionLocal()
        config = session_hdr.query(SchoolConfig).first()
        first_day = date(year, month, 1)
        week0_start = first_day - timedelta(days=start_column)
        row_headers = []
        for row in range(self.calendar_table.rowCount()):
            week_start = week0_start + timedelta(days=7 * row)
            week_end = week_start + timedelta(days=6)
            label = ""
            if config and config.start_date:
                if week_end >= config.start_date and (not config.end_date or week_start <= config.end_date):
                    # label based on week_end to ensure start week is W1
                    week_num = ((week_end - config.start_date).days // 7) + 1
                    label = f"W{week_num}"
            row_headers.append(label)
        self.calendar_table.setVerticalHeaderLabels(row_headers)
        session_hdr.close()
        # auto-adjust row heights to fit lesson widgets
        self.calendar_table.resizeRowsToContents()
        # refresh dashboard after updating calendar
        self.refresh_summary()

    def show_prev_month(self):
        self.current_date = self.current_date.addMonths(-1)
        self.update_calendar()

    def show_next_month(self):
        self.current_date = self.current_date.addMonths(1)
        self.update_calendar()

    def handle_cell_double_click(self, row, col):
        it = self.calendar_table.item(row,col)
        if not it or not it.text().isdigit(): return
        d = int(it.text()); click = date(self.current_date.year(), self.current_date.month(), d)
        lid = self.schedule_map.get(click)
        if lid:
            dlg=LessonDetailDialog(self, lid)
            if dlg.exec_()==QDialog.Accepted: self.update_calendar()

    def open_lesson(self, lesson_id):
        dlg = LessonDetailDialog(self, lesson_id)
        if dlg.exec_() == QDialog.Accepted:
            self.update_calendar()

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
        # ensure calendar grid is updated with full schedule_map
        self.update_calendar()
        # find and display lesson month
        for d, entries in self.schedule_map.items():
            if any(l.id == lesson.id for l, _ in entries):
                self.current_date = QDate(d.year, d.month, d.day)
                self.update_calendar()
                return
        QMessageBox.information(self, "Not scheduled", "Lesson not found in calendar")
