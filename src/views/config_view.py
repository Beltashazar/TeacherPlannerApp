from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QFileDialog, QListWidget, QListWidgetItem, QCalendarWidget, QDateEdit, QDialog, QComboBox, QDialogButtonBox, QTableWidget, QTableWidgetItem, QInputDialog, QColorDialog, QCheckBox, QMessageBox, QGroupBox, QTextEdit, QFormLayout, QLayout, QAbstractScrollArea, QSizePolicy, QFrame, QGridLayout, QScrollArea
from PyQt5.QtCore import Qt, QDate, QRect, QUrl, QTimer
from PyQt5.QtGui import QPainter, QTextCharFormat, QBrush, QColor, QLinearGradient, QGradient, QPixmap, QFont, QDesktopServices, QTextListFormat
import os
import shutil
from database import SessionLocal
from models import SchoolConfig, ClassSubject, CalendarEvent, EventType, RosterEntry, Lesson, LessonPerformance
from functools import partial
import random
from datetime import timedelta
from .lesson_detail_dialog import LessonDetailDialog

class ConfigView(QWidget):
    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout()
        self.logo_path = None
        # track previous start/end dates to clear old formatting
        self.prev_start_qdate = None
        self.prev_end_qdate = None
        # track currently marked dates to clear on reload
        self.current_event_dates = set()
        # place-holder for event types (legend)
        self.event_types = []

        # School Information Section with Calendar
        school_layout = QVBoxLayout()
        # Logo preview
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        school_layout.addWidget(self.logo_label)
        school_info_label = QLabel("School Information")
        school_info_label.setAlignment(Qt.AlignCenter)
        self.school_name_input = QLineEdit()
        self.school_name_input.setPlaceholderText("School Name")
        self.school_name_input.setMaximumWidth(300)
        self.teacher_name_input = QLineEdit()
        self.teacher_name_input.setPlaceholderText("Teacher Name")
        self.teacher_name_input.setMaximumWidth(300)
        # Date pickers for start/end dates
        self.start_date_input = QDateEdit()
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDisplayFormat("yyyy-MM-dd")
        self.start_date_input.setMaximumWidth(300)
        self.end_date_input = QDateEdit()
        self.end_date_input.setCalendarPopup(True)
        self.end_date_input.setDisplayFormat("yyyy-MM-dd")
        self.end_date_input.setMaximumWidth(300)
        self.logo_button = QPushButton("Upload School Logo")
        self.logo_button.clicked.connect(self.upload_logo)
        self.logo_button.setMaximumWidth(300)
        for w in [school_info_label, self.school_name_input, self.teacher_name_input,
                  self.start_date_input, self.end_date_input, self.logo_button]:
            school_layout.addWidget(w)

        self.calendar = SplitCalendarWidget()
        self.calendar.setGridVisible(True)
        # hide built-in week header (we’ll draw custom week numbers)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        # Link date pickers and calendar
        self.start_date_input.dateChanged.connect(self.on_start_date_changed)
        self.end_date_input.dateChanged.connect(self.on_end_date_changed)
        self.calendar.clicked.connect(self.on_calendar_date_clicked)

        # Legend layout for color key
        self.legend_layout = QVBoxLayout()

        # Arrange school info, calendar, and legend side by side
        info_calendar_layout = QHBoxLayout()
        info_calendar_layout.addLayout(school_layout)
        info_calendar_layout.addWidget(self.calendar)
        info_calendar_layout.addLayout(self.legend_layout)
        self.layout.addLayout(info_calendar_layout)

        # Subjects/Classes Section
        class_info_label = QLabel("Classes / Subjects")
        class_info_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(class_info_label)
        # Initialize roster controls
        self.same_roster_checkbox = QCheckBox("All classes share same roster")
        self.same_roster_checkbox.stateChanged.connect(self.on_same_roster_toggled)
        self.global_roster_button = QPushButton("Define Roster")
        self.global_roster_button.clicked.connect(self.define_global_roster)
        self.global_roster_button.hide()
        self.global_roster_button.setMaximumWidth(300)
        # Roster controls above class entry
        self.layout.addWidget(self.same_roster_checkbox)
        self.layout.addWidget(self.global_roster_button)
        # Class entry fields
        self.class_name_input = QLineEdit()
        self.class_name_input.setPlaceholderText("Class/Subject Name")
        self.class_name_input.setMaximumWidth(300)
        self.class_section_input = QLineEdit()
        self.class_section_input.setPlaceholderText("Section (optional)")
        self.class_section_input.setMaximumWidth(300)
        self.add_class_button = QPushButton("Add Class/Subject")
        self.add_class_button.clicked.connect(self.add_class)
        self.add_class_button.setMaximumWidth(300)
        self.layout.addWidget(self.class_name_input)
        self.layout.addWidget(self.class_section_input)
        self.layout.addWidget(self.add_class_button)
        # Class list
        self.class_list = QListWidget()
        self.layout.addWidget(self.class_list)
        self.setLayout(self.layout)
        self.load_config()
        # Load and render legend entries before calendar events
        self.load_event_types()
        # Load any saved calendar events
        self.load_calendar_events()
        # Connect save_config after initial load to prevent clearing data
        self.school_name_input.textChanged.connect(self.save_config)
        self.teacher_name_input.textChanged.connect(self.save_config)
        self.start_date_input.dateChanged.connect(self.save_config)
        self.end_date_input.dateChanged.connect(self.save_config)

    def upload_logo(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Upload School Logo", "", "Image Files (*.png *.jpg *.jpeg)", options=options)
        if file_name:
            self.logo_path = file_name
            self.logo_button.setText(os.path.basename(file_name))
            pixmap = QPixmap(file_name)
            pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
            print(f"Logo uploaded: {file_name}")
            self.save_config()

    def add_class(self):
        name = self.class_name_input.text()
        section = self.class_section_input.text()
        if name:
            widget = ClassItemWidget(name, section)
            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self.class_list.addItem(item)
            self.class_list.setItemWidget(item, widget)
            widget.remove_btn.clicked.connect(lambda _, i=item: self.remove_class(i))
            widget.scope_btn.clicked.connect(partial(self.open_sequence_dialog_for_widget, widget))
            widget.roster_btn.clicked.connect(partial(self.open_roster_dialog_for_widget, widget))
            widget.start_date_edit.dateChanged.connect(lambda qd, w=widget: self.on_class_start_date_changed(w, qd))
            widget.color_btn.clicked.connect(lambda _, w=widget: self.on_edit_color(w))
            self.class_name_input.clear()
            self.class_section_input.clear()
            if self.same_roster_checkbox.isChecked():
                widget.roster_btn.hide()
            # Add class subject to database immediately
            start_date = widget.start_date_edit.date().toPyDate()
            session = SessionLocal()
            try:
                class_subject = ClassSubject(name=name, section=section, start_date=start_date)
                session.add(class_subject)
                session.commit()
                print(f"Successfully added and committed class subject: {name} ({section})")
            except Exception as e:
                print(f"Error adding class subject to database: {e}")
                session.rollback()
            finally:
                session.close()
            # synchronize start date into calendar_event table
            es = SessionLocal()
            cl = widget.label.text()
            ev = es.query(CalendarEvent).filter_by(event_type=cl).first()
            if ev:
                ev.date = start_date
            else:
                es.add(CalendarEvent(date=start_date, event_type=cl))
            es.commit()
            es.close()
            # Add event type for this class to calendar legend if not exists
            class_label = widget.label.text()
            session = SessionLocal()
            try:
                existing = session.query(EventType).filter_by(name=class_label).first()
                if not existing:
                    color = "#{:06x}".format(random.randrange(0x1000000))
                    et = EventType(name=class_label, color=color)
                    session.add(et)
                    session.commit()
                    print(f"Successfully added event type for class label: {class_label}")
            except Exception as e:
                print(f"Error adding event type for class label: {e}")
                session.rollback()
            finally:
                session.close()
            # Apply the event type color to this class row
            color = existing.color if existing else "#D3D3D3"
            item.setBackground(QBrush(QColor(color)))
            self.load_event_types()
            # refresh calendar with class start dates
            self.load_calendar_events()
            # reset start date picker
            self.class_name_input.clear()
            self.class_section_input.clear()

    def load_config(self):
        session = SessionLocal()
        print("Opening session for loading class subjects.")
        config = session.query(SchoolConfig).first()
        if config:
            self.school_name_input.setText(config.school_name or "")
            self.teacher_name_input.setText(config.teacher_name or "")
            if config.start_date:
                qstart = QDate(config.start_date.year, config.start_date.month, config.start_date.day)
                self.start_date_input.setDate(qstart)
                self.prev_start_qdate = qstart
            if config.end_date:
                qend = QDate(config.end_date.year, config.end_date.month, config.end_date.day)
                self.end_date_input.setDate(qend)
                self.prev_end_qdate = qend
            self.logo_path = config.logo_path
            if self.logo_path:
                self.logo_button.setText(os.path.basename(self.logo_path))
                pixmap = QPixmap(self.logo_path)
                pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.logo_label.setPixmap(pixmap)
            # restore shared-roster setting without triggering prompt
            self.same_roster_checkbox.blockSignals(True)
            self.same_roster_checkbox.setChecked(config.all_shared_roster)
            self.same_roster_checkbox.blockSignals(False)
        subjects = session.query(ClassSubject).all()
        print(f"Retrieved {len(subjects)} class subjects from database.")
        self.class_list.clear()
        for subj in subjects:
            print(f"Adding class subject: {subj.name} ({subj.section})")
            widget = ClassItemWidget(subj.name, subj.section, subj.start_date)
            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            self.class_list.addItem(item)
            self.class_list.setItemWidget(item, widget)
            widget.remove_btn.clicked.connect(lambda _, i=item: self.remove_class(i))
            widget.scope_btn.clicked.connect(partial(self.open_sequence_dialog_for_widget, widget))
            widget.roster_btn.clicked.connect(partial(self.open_roster_dialog_for_widget, widget))
            widget.start_date_edit.dateChanged.connect(lambda qd, w=widget: self.on_class_start_date_changed(w, qd))
            widget.color_btn.clicked.connect(lambda _, w=widget: self.on_edit_color(w))
            if self.same_roster_checkbox.isChecked():
                widget.roster_btn.hide()
            # color class row by corresponding event type color
            et = session.query(EventType).filter_by(name=widget.label.text()).first()
            if et:
                item.setBackground(QBrush(QColor(et.color)))
            else:
                item.setBackground(QBrush(QColor("#FFFFFF")))
        session.close()
        print("Session closed after loading class subjects.")
        # ensure global roster button reflects saved setting
        self.global_roster_button.setVisible(config.all_shared_roster if config else False)

    def save_config(self):
        session = SessionLocal()
        config = session.query(SchoolConfig).first()
        if not config:
            config = SchoolConfig()
            session.add(config)
        config.school_name = self.school_name_input.text()
        config.teacher_name = self.teacher_name_input.text()
        config.start_date = self.start_date_input.date().toPyDate()
        config.end_date = self.end_date_input.date().toPyDate()
        config.logo_path = self.logo_path
        config.all_shared_roster = self.same_roster_checkbox.isChecked()
        try:
            session.commit()
            print("Successfully committed school configuration.")
        except Exception as e:
            print(f"Error committing school configuration - {e}")
        # sync ClassSubject entries (unique by name)
        existing = {s.name: s for s in session.query(ClassSubject).all()}
        current_names = set()
        for i in range(self.class_list.count()):
            widget = self.class_list.itemWidget(self.class_list.item(i))
            name = widget.name
            section = widget.section or None
            current_names.add(name)
            print(f"Saving class subject: {name} ({section})")
            if name not in existing:
                session.add(ClassSubject(name=name, section=section))
            else:
                existing[name].section = section
        for name, obj in existing.items():
            if name not in current_names:
                session.delete(obj)
        try:
            session.commit()
            print("Successfully committed class subjects.")
        except Exception as e:
            print(f"Error committing class subjects - {e}")
        session.close()
        print("Configuration updated.")

    def on_start_date_changed(self, qdate):
        # reload calendar to reflect start date changes
        if self.prev_start_qdate and self.prev_start_qdate != qdate:
            self.current_event_dates.discard(self.prev_start_qdate)
        self.prev_start_qdate = qdate
        self.load_calendar_events()
        # ensure calendar view updates immediately
        try:
            self.calendar.updateCells()
        except AttributeError:
            self.calendar.repaint()

    def on_end_date_changed(self, qdate):
        # reload calendar to reflect end date changes
        if self.prev_end_qdate and self.prev_end_qdate != qdate:
            self.current_event_dates.discard(self.prev_end_qdate)
        self.prev_end_qdate = qdate
        self.load_calendar_events()
        # ensure calendar view updates immediately
        try:
            self.calendar.updateCells()
        except AttributeError:
            self.calendar.repaint()

    def on_calendar_date_clicked(self, qdate):
        dlg = QDialog(self)
        dlg.setWindowTitle("Select Calendar Action")
        layout = QVBoxLayout()
        combo = QComboBox()
        combo.addItems([et.name for et in self.event_types])
        layout.addWidget(QLabel("Event Type:"))
        layout.addWidget(combo)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Event")
        remove_one_btn = QPushButton("Remove One")
        remove_all_btn = QPushButton("Remove All")
        cancel_btn = QPushButton("Cancel")
        for btn in (add_btn, remove_one_btn, remove_all_btn, cancel_btn):
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)
        dlg.setLayout(layout)
        # handlers for calendar event actions
        def on_add():
            etype = combo.currentText()
            date_py = qdate.toPyDate()
            session = SessionLocal()
            # upsert class start event: keep only one per event_type
            ev = session.query(CalendarEvent).filter_by(event_type=etype).first()
            if ev:
                ev.date = date_py
            else:
                ev = CalendarEvent(date=date_py, event_type=etype)
                session.add(ev)
            try:
                session.commit()
                print(f"Successfully committed calendar event: {etype} on {date_py}")
            except Exception as e:
                print(f"Error committing calendar event: {etype} on {date_py} - {e}")
            session.close()
            # update class start_date if class event
            if "(" in etype and etype.endswith(")"):
                base, sec = etype.rsplit("(", 1)
                cs_name = base.strip()
                cs_section = sec[:-1]
                session2 = SessionLocal()
                cs = session2.query(ClassSubject).filter_by(name=cs_name, section=cs_section).first()
                if cs:
                    cs.start_date = date_py
                    try:
                        session2.commit()
                        print(f"Successfully committed class start date: {cs_name} ({cs_section}) on {date_py}")
                    except Exception as e:
                        print(f"Error committing class start date: {cs_name} ({cs_section}) on {date_py} - {e}")
                session2.close()
            # update inline class start_date editor
            for i in range(self.class_list.count()):
                item = self.class_list.item(i)
                w = self.class_list.itemWidget(item)
                if w and w.label.text() == etype:
                    w.start_date_edit.setDate(QDate(date_py.year, date_py.month, date_py.day))
                    break
            self.load_calendar_events()
            dlg.accept()
        def on_remove_one():
            date_py = qdate.toPyDate()
            session = SessionLocal()
            evs = session.query(CalendarEvent).filter(CalendarEvent.date==date_py).all()
            session.close()
            if not evs:
                QMessageBox.information(self, "Remove Event", "No events on this date.")
                return
            items = [ev.event_type for ev in evs]
            choice, ok = QInputDialog.getItem(self, "Remove Event", "Select event to remove:", items, 0, False)
            if ok and choice:
                sess = SessionLocal()
                ev = sess.query(CalendarEvent).filter(CalendarEvent.date==date_py, CalendarEvent.event_type==choice).first()
                if ev:
                    sess.delete(ev)
                    try:
                        sess.commit()
                        print(f"Successfully committed removal of calendar event: {choice} on {date_py}")
                    except Exception as e:
                        print(f"Error committing removal of calendar event: {choice} on {date_py} - {e}")
                sess.close()
                self.load_calendar_events()
                dlg.accept()
        def on_remove_all():
            date_py = qdate.toPyDate()
            session = SessionLocal()
            session.query(CalendarEvent).filter(CalendarEvent.date==date_py).delete()
            try:
                session.commit()
                print(f"Successfully committed removal of all calendar events on {date_py}")
            except Exception as e:
                print(f"Error committing removal of all calendar events on {date_py} - {e}")
            session.close()
            self.load_calendar_events()
            dlg.accept()
        add_btn.clicked.connect(on_add)
        remove_one_btn.clicked.connect(on_remove_one)
        remove_all_btn.clicked.connect(on_remove_all)
        cancel_btn.clicked.connect(dlg.reject)
        dlg.exec_()
        # if dlg.exec_() == QDialog.Accepted:
        #     event_type = combo.currentText()
        #     date = qdate.toPyDate()
        #     session = SessionLocal()
        #     ev = session.query(CalendarEvent).filter(CalendarEvent.date == date).first()
        #     # clear event if user selected None
        #     if event_type == "None":
        #         if ev:
        #             session.delete(ev)
        #             session.commit()
        #         session.close()
        #         # clear formatting for this date
        #         self.calendar.setDateTextFormat(qdate, QTextCharFormat())
        #         self.current_event_dates.discard(qdate)
        #         return
        #     if not ev:
        #         ev = CalendarEvent(date=date, event_type=event_type)
        #         session.add(ev)
        #     else:
        #         ev.event_type = event_type
        #     session.commit()
        #     session.close()
        #     # update class subject start date if this event is a class
        #     session2 = SessionLocal()
        #     if "(" in event_type and event_type.endswith(")"):
        #         base, sec = event_type.rsplit("(", 1)
        #         cs_name = base.strip()
        #         cs_section = sec[:-1]
        #     else:
        #         cs_name = event_type
        #         cs_section = None
        #     cs = session2.query(ClassSubject).filter_by(name=cs_name, section=cs_section).first()
        #     if cs:
        #         cs.start_date = date
        #         session2.commit()
        #     session2.close()
        #     self.mark_event_on_calendar(qdate, event_type)

    def mark_event_on_calendar(self, qdate, event_type):
        fmt = QTextCharFormat()
        # dynamic color lookup from EventType table
        session = SessionLocal()
        et = session.query(EventType).filter(EventType.name == event_type).first()
        session.close()
        color = et.color if et else "#D3D3D3"
        fmt.setBackground(QBrush(QColor(color)))
        self.calendar.setDateTextFormat(qdate, fmt)
        self.current_event_dates.add(qdate)

    def load_calendar_events(self):
        # debug: log loaded calendar events
        session_debug = SessionLocal()
        events_debug = session_debug.query(CalendarEvent).all()
        print(f"Loaded {len(events_debug)} calendar events from DB: {[ (e.date, e.event_type) for e in events_debug ]}")
        session_debug.close()
        # rebuild cell color splits
        self.calendar.date_colors.clear()
        session = SessionLocal()
        events = session.query(CalendarEvent).all()
        session.close()
        events_by_date = {}
        for ev in events:
            events_by_date.setdefault(ev.date, []).append(ev.event_type)
        # include start/end dates from selectors
        start_py = self.start_date_input.date().toPyDate()
        events_by_date.setdefault(start_py, []).append("Start Date")
        end_py = self.end_date_input.date().toPyDate()
        events_by_date.setdefault(end_py, []).append("End Date")
        # include class subject start dates
        session2 = SessionLocal()
        for subj in session2.query(ClassSubject).filter(ClassSubject.start_date != None).all():
            label = f'{subj.name} ({subj.section})' if subj.section else subj.name
            events_by_date.setdefault(subj.start_date, []).append(label)
        session2.close()
        for date_py, types in events_by_date.items():
            qdate = QDate(date_py.year, date_py.month, date_py.day)
            colors = [next((et.color for et in self.event_types if et.name == t), "#D3D3D3") for t in types]
            self.calendar.setDateColors(qdate, colors)
        self.current_event_dates = set(events_by_date.keys())
        # force full calendar repaint to clear old cells
        self.calendar.updateCells()
        # no built-in week header updates needed

    def load_event_types(self):
        # ensure default and class event types exist, then render
        session = SessionLocal()
        # default types
        if not session.query(EventType).count():
            default_defs = {
                "Vacation/Holiday": "#ADD8E6",
                "In Service Day": "#90EE90",
                "Parent Conference": "#FFFF00",
                "School Event": "#F08080",
                "Start Date": "#00FF00",
                "End Date": "#FF0000"
            }
            for name, color in default_defs.items():
                session.add(EventType(name=name, color=color))
        # class subjects
        for subj in session.query(ClassSubject).all():
            label = f"{subj.name} ({subj.section})" if subj.section else subj.name
            if not session.query(EventType).filter_by(name=label).first():
                color = "#{:06x}".format(random.randrange(0x1000000))
                session.add(EventType(name=label, color=color))
        try:
            session.commit()
            print("Successfully committed event types.")
        except Exception as e:
            print(f"Error committing event types - {e}")
        types = session.query(EventType).all()
        session.close()
        self.event_types = types
        self.render_legend()
        # update class list row colors after legend changes
        self.update_class_list_colors()

    def render_legend(self):
        # clear existing legend entries
        self.clearLayout(self.legend_layout)
        # header
        legend_label = QLabel("Legend:")
        self.legend_layout.addWidget(legend_label)
        # each type as a horizontal row
        for et in self.event_types:
            row = QHBoxLayout()
            swatch = QLabel()
            swatch.setFixedSize(15,15)
            swatch.setStyleSheet(f"background-color: {et.color}")
            name_label = QLabel(et.name)
            row.addWidget(swatch)
            row.addWidget(name_label)
            self.legend_layout.addLayout(row)
        # spacer pushes the manage button to bottom
        self.legend_layout.addStretch()
        manage_btn = QPushButton("Manage Types")
        manage_btn.clicked.connect(self.open_manage_types_dialog)
        self.legend_layout.addWidget(manage_btn)

    def clearLayout(self, layout):
        """
        Recursively clear all items from a layout, including nested layouts.
        """
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clearLayout(child.layout())
                child.layout().deleteLater()

    def open_manage_types_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Manage Event Types")
        layout = QVBoxLayout()
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Type Name", "Color"])
        session = SessionLocal()
        types = session.query(EventType).all()
        for row, et in enumerate(types):
            table.insertRow(row)
            name_item = QTableWidgetItem(et.name)
            table.setItem(row, 0, name_item)
            color_item = QTableWidgetItem(et.color)
            color_item.setBackground(QBrush(QColor(et.color)))
            table.setItem(row, 1, color_item)
        session.close()
        layout.addWidget(table)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add")
        remove_btn = QPushButton("Remove")
        edit_btn = QPushButton("Edit Color")
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(edit_btn)
        layout.addLayout(btn_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        dlg.setLayout(layout)

        def add_type():
            text, ok = QInputDialog.getText(self, "New Type", "Enter event type name:")
            if ok and text:
                color = QColorDialog.getColor()
                if color.isValid():
                    session = SessionLocal()
                    et = EventType(name=text, color=color.name())
                    session.add(et)
                    try:
                        session.commit()
                        print(f"Successfully committed new event type: {text}")
                    except Exception as e:
                        print(f"Error committing new event type: {text} - {e}")
                    session.close()
                    self.load_event_types()
                    row = table.rowCount()
                    table.insertRow(row)
                    name_item = QTableWidgetItem(text)
                    color_item = QTableWidgetItem(color.name())
                    color_item.setBackground(QBrush(color))
                    table.setItem(row,0,name_item)
                    table.setItem(row,1,color_item)

        def remove_type():
            row = table.currentRow()
            if row >= 0:
                name = table.item(row,0).text()
                session = SessionLocal()
                et = session.query(EventType).filter_by(name=name).first()
                if et:
                    session.delete(et)
                    # remove associated calendar events
                    session.query(CalendarEvent).filter(CalendarEvent.event_type==name).delete()
                    try:
                        session.commit()
                        print(f"Successfully committed removal of event type: {name}")
                    except Exception as e:
                        print(f"Error committing removal of event type: {name} - {e}")
                session.close()
                table.removeRow(row)
                self.load_event_types()
                self.load_calendar_events()

        def edit_color():
            row = table.currentRow()
            if row >= 0:
                name = table.item(row,0).text()
                session = SessionLocal()
                et = session.query(EventType).filter(EventType.name==name).first()
                session.close()
                if et:
                    color = QColorDialog.getColor(QColor(et.color), self, f"Choose color for {name}")
                    if color.isValid():
                        session = SessionLocal()
                        et_db = session.query(EventType).filter(EventType.name==name).first()
                        et_db.color = color.name()
                        try:
                            session.commit()
                            print(f"Successfully committed color change for event type: {name}")
                        except Exception as e:
                            print(f"Error committing color change for event type: {name} - {e}")
                        session.close()
                        table.item(row,1).setBackground(QBrush(color))
                        table.item(row,1).setText(color.name())
                        self.load_event_types()
                        self.load_calendar_events()

        add_btn.clicked.connect(add_type)
        remove_btn.clicked.connect(remove_type)
        edit_btn.clicked.connect(edit_color)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        dlg.exec_()
        # self.adjustSize()

    def open_weekly_view(self, class_subject_id):
        from .weekly_view_dialog import WeeklyViewDialog
        dlg = WeeklyViewDialog(self, class_subject_id)
        dlg.exec_()

    def on_same_roster_toggled(self, state):
        same = state == Qt.Checked
        # confirmation dialog
        msg = "Combine individual rosters into one global roster?" if same else "Propagate global roster to all classes?"
        reply = QMessageBox.question(self, "Confirm Roster Change", msg, QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            # revert checkbox
            self.same_roster_checkbox.blockSignals(True)
            self.same_roster_checkbox.setChecked(not same)
            self.same_roster_checkbox.blockSignals(False)
            return
        for i in range(self.class_list.count()):
            item = self.class_list.item(i)
            widget = self.class_list.itemWidget(item)
            if widget:
                widget.roster_btn.setVisible(not same)
        self.global_roster_button.setVisible(same)
        # migrate roster entries
        session = SessionLocal()
        if same:
            # combine individual into global (remove duplicates)
            names = {r.name for r in session.query(RosterEntry).filter(RosterEntry.class_subject_id.isnot(None)).all()}
            # clear old global entries
            session.query(RosterEntry).filter(RosterEntry.class_subject_id == None).delete()
            for name in names:
                session.add(RosterEntry(class_subject_id=None, name=name))
        else:
            # propagate global to each class
            global_names = [r.name for r in session.query(RosterEntry).filter(RosterEntry.class_subject_id.is_(None)).all()]
            for cs in session.query(ClassSubject).all():
                session.query(RosterEntry).filter(RosterEntry.class_subject_id == cs.id).delete()
                for name in global_names:
                    session.add(RosterEntry(class_subject_id=cs.id, name=name))
        try:
            session.commit()
            print("Successfully committed roster changes.")
        except Exception as e:
            print(f"Error committing roster changes - {e}")
        session.close()
        self.save_config()

    def define_global_roster(self):
        self.open_roster_dialog(None, "Global Roster")

    def open_sequence_dialog_for_widget(self, widget):
        session = SessionLocal()
        cs = session.query(ClassSubject).filter_by(name=widget.name, section=widget.section).first()
        session.close()
        if cs:
            title = f"Scope & Sequence for {widget.name}" + (f" ({widget.section})" if widget.section else "")
            self.open_sequence_dialog(cs.id, title)

    def open_sequence_dialog(self, class_subject_id, title):
        dlg = SequenceDialog(self, class_subject_id, title)
        dlg.exec_()

    def open_roster_dialog_for_widget(self, widget):
        session = SessionLocal()
        cs = session.query(ClassSubject).filter_by(name=widget.name, section=widget.section).first()
        session.close()
        if cs:
            title = f"Roster for {widget.name}" + (f" ({widget.section})" if widget.section else "")
            self.open_roster_dialog(cs.id, title)

    def open_roster_dialog(self, class_subject_id, title):
        dlg = RosterDialog(self, class_subject_id, title)
        dlg.exec_()

    def remove_class(self, item):
        # remove class list item and its DB entries
        row = self.class_list.row(item)
        widget = self.class_list.itemWidget(item)
        class_label = widget.label.text()
        self.class_list.takeItem(row)
        session = SessionLocal()
        cs = session.query(ClassSubject).filter_by(name=widget.name, section=widget.section).first()
        if cs:
            session.delete(cs)
        et = session.query(EventType).filter_by(name=class_label).first()
        if et:
            session.delete(et)
        # remove associated calendar events
        session.query(CalendarEvent).filter(CalendarEvent.event_type==class_label).delete()
        try:
            session.commit()
            print(f"Successfully committed removal of class subject: {widget.name} ({widget.section})")
        except Exception as e:
            print(f"Error committing removal of class subject: {widget.name} ({widget.section}) - {e}")
        session.close()
        # refresh legend and calendar
        self.load_event_types()
        self.load_calendar_events()

    def cycle_status(self, btn):
        seq = ["", "Green", "Yellow", "Red"]
        idx = seq.index(btn._status)
        idx = (idx + 1) % len(seq)
        btn._status = seq[idx]
        if btn._status:
            btn.setStyleSheet(f"color: {btn._status.lower()};")
        else:
            btn.setStyleSheet("")

    def update_class_list_colors(self):
        for i in range(self.class_list.count()):
            item = self.class_list.item(i)
            widget = self.class_list.itemWidget(item)
            if widget:
                class_label = widget.label.text()
                session = SessionLocal()
                et = session.query(EventType).filter_by(name=class_label).first()
                session.close()
                if et:
                    item.setBackground(QBrush(QColor(et.color)))

    def update_week_numbers(self, year=None, month=None):
        """Update custom week numbers based on school start/end dates"""
        from PyQt5.QtWidgets import QTableView
        # get internal table view and vertical header
        tv = self.calendar.findChild(QTableView)
        if not tv:
            return
        header = tv.verticalHeader()
        # compute first Monday displayed
        y = self.calendar.yearShown()
        m = self.calendar.monthShown()
        fd = QDate(y, m, 1)
        offset = fd.dayOfWeek() - 1
        first_monday = fd.addDays(-offset)
        sd_py = self.start_date_input.date().toPyDate()
        ed_py = self.end_date_input.date().toPyDate()
        # compute start-of-school week Monday
        sd_week_start = sd_py - timedelta(days=sd_py.weekday())
        rows = header.count()
        for i in range(rows):
            mon = first_monday.addDays(i * 7)
            mon_py = mon.toPyDate()
            if sd_py <= mon_py <= ed_py:
                wk_num = ((mon_py - sd_week_start).days // 7) + 1
                header.model().setHeaderData(i, Qt.Vertical, wk_num, Qt.DisplayRole)
            else:
                header.model().setHeaderData(i, Qt.Vertical, "", Qt.DisplayRole)

    def on_class_start_date_changed(self, widget, qdate):
        session = SessionLocal()
        cs = session.query(ClassSubject).filter_by(name=widget.name, section=widget.section).first()
        new_date = qdate.toPyDate()
        cs.start_date = new_date
        # update or insert CalendarEvent for this class start
        cl = widget.label.text()
        ev = session.query(CalendarEvent).filter_by(event_type=cl).first()
        if ev:
            ev.date = new_date
        else:
            session.add(CalendarEvent(date=new_date, event_type=cl))
        session.commit()
        session.close()
        # refresh calendar to show updated dates
        self.load_calendar_events()

    def cycle_status(self, btn):
        seq = ["", "Green", "Yellow", "Red"]
        idx = seq.index(btn._status)
        idx = (idx + 1) % len(seq)
        btn._status = seq[idx]
        if btn._status:
            btn.setStyleSheet(f"color: {btn._status.lower()};")
        else:
            btn.setStyleSheet("")

    def update_class_list_colors(self):
        for i in range(self.class_list.count()):
            item = self.class_list.item(i)
            widget = self.class_list.itemWidget(item)
            if widget:
                class_label = widget.label.text()
                session = SessionLocal()
                et = session.query(EventType).filter_by(name=class_label).first()
                session.close()
                if et:
                    item.setBackground(QBrush(QColor(et.color)))

    def update_week_numbers(self, year=None, month=None):
        """Update custom week numbers based on school start/end dates"""
        from PyQt5.QtWidgets import QTableView
        # get internal table view and vertical header
        tv = self.calendar.findChild(QTableView)
        if not tv:
            return
        header = tv.verticalHeader()
        # compute first Monday displayed
        y = self.calendar.yearShown()
        m = self.calendar.monthShown()
        fd = QDate(y, m, 1)
        offset = fd.dayOfWeek() - 1
        first_monday = fd.addDays(-offset)
        sd_py = self.start_date_input.date().toPyDate()
        ed_py = self.end_date_input.date().toPyDate()
        # compute start-of-school week Monday
        sd_week_start = sd_py - timedelta(days=sd_py.weekday())
        rows = header.count()
        for i in range(rows):
            mon = first_monday.addDays(i * 7)
            mon_py = mon.toPyDate()
            if sd_py <= mon_py <= ed_py:
                wk_num = ((mon_py - sd_week_start).days // 7) + 1
                header.model().setHeaderData(i, Qt.Vertical, wk_num, Qt.DisplayRole)
            else:
                header.model().setHeaderData(i, Qt.Vertical, "", Qt.DisplayRole)

    def on_edit_color(self, widget):
        # Open color picker and update class event type
        session = SessionLocal()
        et = session.query(EventType).filter_by(name=widget.label.text()).first()
        initial = QColor(et.color) if et else QColor("#D3D3D3")
        color = QColorDialog.getColor(initial, self, "Select Class Color")
        if color.isValid():
            if et:
                et.color = color.name()
            else:
                et = EventType(name=widget.label.text(), color=color.name())
                session.add(et)
            session.commit()
        session.close()
        # Reflect color in UI
        widget.color_btn.setStyleSheet(f"background-color: {color.name()}")
        self.load_event_types()
        self.load_calendar_events()
        self.update_class_list_colors()

class SplitCalendarWidget(QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.date_colors = {}

    def setDateColors(self, qdate, colors):
        self.date_colors[qdate] = colors
        self.updateCell(qdate)

    def paintCell(self, painter, rect, date):
        # draw colored background splits or default background
        if date in self.date_colors:
            colors = self.date_colors[date]
            painter.save()
            if len(colors) == 1:
                painter.fillRect(rect, QColor(colors[0]))
            else:
                half = rect.width() // 2
                left_rect = QRect(rect.left(), rect.top(), half, rect.height())
                right_rect = QRect(rect.left() + half, rect.top(), rect.width() - half, rect.height())
                painter.fillRect(left_rect, QColor(colors[0]))
                painter.fillRect(right_rect, QColor(colors[1] if len(colors) > 1 else colors[0]))
            painter.restore()
            # draw day number
            painter.save()
            painter.setPen(Qt.black)
            painter.drawText(rect, Qt.AlignCenter, str(date.day()))
            painter.restore()
        else:
            super().paintCell(painter, rect, date)

        # custom week number on Mondays within school dates
        if date.dayOfWeek() == Qt.Monday:
            parent = self.parent()
            if hasattr(parent, 'start_date_input'):
                sd_py = parent.start_date_input.date().toPyDate()
                ed_py = parent.end_date_input.date().toPyDate()
                # compute start-of-school week Monday
                sd_week_start = sd_py - timedelta(days=sd_py.weekday())
                date_py = date.toPyDate()
                if sd_py <= date_py <= ed_py:
                    wk_num = ((date_py - sd_week_start).days // 7) + 1
                    painter.save()
                    painter.setPen(Qt.gray)
                    painter.setFont(QFont('Arial', 8))
                    painter.drawText(rect.adjusted(4, 2, 0, 0), Qt.AlignLeft | Qt.AlignTop, str(wk_num))
                    painter.restore()

class ClassItemWidget(QWidget):
    def __init__(self, name, section, start_date=None):
        super().__init__()
        self.name = name
        self.section = section
        layout = QHBoxLayout()
        label_text = f"{name} ({section})" if section else name
        self.label = QLabel(label_text)
        self.start_date_label = QLabel("Start Date:")
        # start date editor for class
        self.start_date_edit = QDateEdit(calendarPopup=True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        if start_date:
            qd = QDate(start_date.year, start_date.month, start_date.day)
            self.start_date_edit.setDate(qd)
        else:
            self.start_date_edit.setDate(QDate.currentDate())
        self.scope_btn = QPushButton("Define Scope & Sequence")
        self.roster_btn = QPushButton("Define Roster")
        self.remove_btn = QPushButton("Remove")
        self.color_btn = QPushButton("Edit Color")
        layout.addWidget(self.label)
        layout.addWidget(self.start_date_label)
        layout.addWidget(self.start_date_edit)
        layout.addWidget(self.scope_btn)
        layout.addWidget(self.roster_btn)
        layout.addWidget(self.remove_btn)
        layout.addWidget(self.color_btn)
        self.setLayout(layout)

class RosterDialog(QDialog):
    def __init__(self, parent, class_subject_id, title):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.class_subject_id = class_subject_id
        self.session = SessionLocal()
        if class_subject_id is None:
            global_names = {r[0] for r in self.session.query(RosterEntry.name).filter(RosterEntry.class_subject_id == None).all()}
            class_names = {r[0] for r in self.session.query(RosterEntry.name).filter(RosterEntry.class_subject_id != None).all()}
            names = sorted(global_names.union(class_names), key=lambda n: n.split()[-1])
        else:
            entries = self.session.query(RosterEntry).filter_by(class_subject_id=class_subject_id).all()
            names = sorted([r.name for r in entries], key=lambda n: n.split()[-1])
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.list_widget = QListWidget()
        for n in names:
            self.list_widget.addItem(QListWidgetItem(n))
        layout.addWidget(self.list_widget)
        input_layout = QHBoxLayout()
        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText("First Name")
        self.first_name_input.setMaximumWidth(300)
        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText("Last Name")
        self.last_name_input.setMaximumWidth(300)
        self.add_btn = QPushButton("Add Student")
        self.add_btn.clicked.connect(self.add_student)
        self.add_btn.setMaximumWidth(300)
        input_layout.addWidget(self.first_name_input)
        input_layout.addWidget(self.last_name_input)
        input_layout.addWidget(self.add_btn)
        layout.addLayout(input_layout)
        self.remove_btn = QPushButton("Remove Student")
        self.remove_btn.clicked.connect(self.remove_student)
        self.remove_btn.setMaximumWidth(300)
        layout.addWidget(self.remove_btn)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.save_and_close)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def add_student(self):
        first_name = self.first_name_input.text().strip()
        last_name = self.last_name_input.text().strip()
        if first_name and last_name:
            full_name = f"{first_name} {last_name}"
            self.list_widget.addItem(full_name)
            self.first_name_input.clear()
            self.last_name_input.clear()
            self.sort_list_widget()

    def sort_list_widget(self):
        names = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        names.sort(key=lambda n: n.split()[-1])
        self.list_widget.clear()
        for name in names:
            self.list_widget.addItem(name)

    def remove_student(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def save_and_close(self):
        if self.class_subject_id is None:
            self.session.query(RosterEntry).filter(RosterEntry.class_subject_id == None).delete()
        else:
            self.session.query(RosterEntry).filter_by(class_subject_id=self.class_subject_id).delete()
        for i in range(self.list_widget.count()):
            name = self.list_widget.item(i).text()
            entry = RosterEntry(class_subject_id=self.class_subject_id, name=name)
            self.session.add(entry)
        try:
            self.session.commit()
            print("Successfully committed roster entries.")
        except Exception as e:
            print(f"Error committing roster entries - {e}")
        self.session.close()
        self.accept()

class SequenceDialog(QDialog):
    def __init__(self, parent, class_subject_id, title):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.class_subject_id = class_subject_id
        self.session = SessionLocal()
        # lesson type and status options for dropdowns
        self.type_options = ["Core","Non-Core","Practice","Assessment"]
        self.status_options = ["Not complete","Complete","Skipped"]
        # main layout and scrollable content area
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        content_widget = QWidget()
        self.scroll.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSizeConstraint(QLayout.SetMinimumSize)
        # Bulk add lessons
        bulk_gb = QGroupBox("Bulk Insert Lessons")
        bulk_layout = QHBoxLayout()
        self.bulk_start = QLineEdit()
        self.bulk_start.setPlaceholderText("Start Number (e.g. 1.1)")
        self.bulk_start.setMaximumWidth(300)
        self.bulk_end = QLineEdit()
        self.bulk_end.setPlaceholderText("End Number (e.g. 1.12)")
        self.bulk_end.setMaximumWidth(300)
        bulk_btn = QPushButton("Insert Range")
        bulk_btn.clicked.connect(self.bulk_add_range)
        bulk_btn.setMaximumWidth(300)
        bulk_layout.addWidget(self.bulk_start)
        bulk_layout.addWidget(self.bulk_end)
        bulk_layout.addWidget(bulk_btn)
        bulk_gb.setLayout(bulk_layout)
        content_layout.addWidget(bulk_gb)
        # single-add and remove buttons
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Insert Lesson")
        rm_sel_btn = QPushButton("Remove Selected")
        rm_all_btn = QPushButton("Remove All")
        merge_btn = QPushButton("Merge Lessons")
        add_btn.setMaximumWidth(300)
        rm_sel_btn.setMaximumWidth(300)
        rm_all_btn.setMaximumWidth(300)
        merge_btn.setMaximumWidth(300)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rm_sel_btn)
        btn_row.addWidget(rm_all_btn)
        btn_row.addWidget(merge_btn)
        content_layout.addLayout(btn_row)
        add_btn.clicked.connect(self.add_single_lesson)
        rm_sel_btn.clicked.connect(self.remove_selected_lessons)
        rm_all_btn.clicked.connect(self.remove_all_lessons)
        merge_btn.clicked.connect(self.merge_selected_lessons)
        # Lessons table with action buttons
        self.table = QTableWidget()
        self.table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels([
            "Select","Lesson Number","Lesson Name","Lesson Objective",
            "Type","Status","Review","Anchor Date","Edit","Remove","Up","Down"
        ])
        lessons = self.session.query(Lesson).filter_by(class_subject_id=class_subject_id).order_by(Lesson.sequence).all()
        self.table.setRowCount(len(lessons))
        self.lesson_ids = []
        for idx, lesson in enumerate(lessons):
            # checkbox
            cb_item = QTableWidgetItem()
            cb_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            cb_item.setCheckState(Qt.Unchecked)
            self.table.setItem(idx,0,cb_item)
            # lesson fields
            self.table.setItem(idx,1,QTableWidgetItem(lesson.number))
            self.table.setItem(idx,2,QTableWidgetItem(lesson.name or ""))
            self.table.setItem(idx,3,QTableWidgetItem(lesson.learning_objective or ""))
            # type dropdown
            type_cb = QComboBox()
            type_cb.addItems(self.type_options)
            type_cb.setEditable(True)
            if lesson.lesson_type:
                i_type = type_cb.findText(lesson.lesson_type)
                if i_type >= 0: type_cb.setCurrentIndex(i_type)
            self.table.setCellWidget(idx,4,type_cb)
            # status dropdown
            status_cb = QComboBox()
            status_cb.addItems(self.status_options)
            status_cb.setEditable(True)
            if lesson.status:
                i_stat = status_cb.findText(lesson.status)
                if i_stat >= 0: status_cb.setCurrentIndex(i_stat)
            self.table.setCellWidget(idx,5,status_cb)
            # review dropdown
            review_cb = QComboBox()
            review_cb.addItems(["Pending","Approved"])
            if lesson.review_status:
                ir = review_cb.findText(lesson.review_status)
                if ir >= 0: review_cb.setCurrentIndex(ir)
            self.table.setCellWidget(idx,6,review_cb)
            # anchor date widget
            anchor_widget = QWidget()
            aw_layout = QHBoxLayout(anchor_widget)
            aw_layout.setContentsMargins(0,0,0,0)
            anchor_cb = QCheckBox()
            anchor_de = QDateEdit(calendarPopup=True)
            anchor_de.setEnabled(False)
            if lesson.anchor_date:
                qd = QDate(lesson.anchor_date.year, lesson.anchor_date.month, lesson.anchor_date.day)
                anchor_cb.setChecked(True)
                anchor_de.setEnabled(True)
                anchor_de.setDate(qd)
            else:
                anchor_cb.setChecked(False)
                anchor_de.setDate(QDate.currentDate())
            anchor_cb.stateChanged.connect(lambda s, de=anchor_de: de.setEnabled(s == Qt.Checked))
            aw_layout.addWidget(anchor_cb)
            aw_layout.addWidget(anchor_de)
            self.table.setCellWidget(idx,7,anchor_widget)
            # action buttons
            edit_btn = QPushButton("Edit")
            edit_btn.clicked.connect(self.on_edit_button_clicked)
            self.table.setCellWidget(idx,8,edit_btn)
            rem_btn = QPushButton("Remove")
            rem_btn.clicked.connect(self.on_remove_button_clicked)
            self.table.setCellWidget(idx,9,rem_btn)
            # add reorder buttons
            up_btn = QPushButton("▲")
            up_btn.clicked.connect(self.move_up_clicked)
            self.table.setCellWidget(idx,10,up_btn)
            down_btn = QPushButton("▼")
            down_btn.clicked.connect(self.move_down_clicked)
            self.table.setCellWidget(idx,11,down_btn)
            self.lesson_ids.append(lesson.id)
        content_layout.addWidget(self.table)
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_and_close)
        buttons.rejected.connect(self.reject)
        content_layout.addWidget(buttons)
        layout.addWidget(self.scroll)
        layout.addWidget(buttons)
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        # ensure dialog width fits all table columns
        total_width = self.table.verticalHeader().width() + sum(self.table.columnWidth(i) for i in range(self.table.columnCount())) + self.table.frameWidth()*2
        self.scroll.setMinimumWidth(total_width)
        self.setMinimumWidth(total_width + 40)
        self.table.resizeRowsToContents()
        self.adjustSize()
        # auto-save inline edits: number, name, objective, type, status, review, anchor_date
        self.table.cellChanged.connect(self._on_sequence_cell_changed)
        for r in range(self.table.rowCount()):
            # lesson_type
            cb_type = self.table.cellWidget(r,4)
            cb_type.currentTextChanged.connect(lambda txt, row=r: self._update_sequence_field(row, 'lesson_type', txt))
            # status
            cb_stat = self.table.cellWidget(r,5)
            cb_stat.currentTextChanged.connect(lambda txt, row=r: self._update_sequence_field(row, 'status', txt))
            # review_status
            cb_rev = self.table.cellWidget(r,6)
            cb_rev.currentTextChanged.connect(lambda txt, row=r: self._update_sequence_field(row, 'review_status', txt))
            # anchor_date
            aw = self.table.cellWidget(r,7)
            cbx = aw.layout().itemAt(0).widget()
            de_anchor = aw.layout().itemAt(1).widget()
            cbx.stateChanged.connect(lambda state, row=r, de=de_anchor: self._update_anchor_date(row, state, de.date()))
            de_anchor.dateChanged.connect(lambda qd, row=r, cb=cbx: self._update_anchor_date(row, Qt.Checked if cb.isChecked() else Qt.Unchecked, qd))

    def bulk_add_range(self):
        start = self.bulk_start.text().strip()
        end = self.bulk_end.text().strip()
        if '.' in start and '.' in end:
            s0, s1 = start.split('.',1)
            e0, e1 = end.split('.',1)
            if s0==e0:
                try: si=int(s1); ei=int(e1)
                except: return
                # insert lessons at selected row or end
                insert_at = self.table.currentRow() if self.table.currentRow() >= 0 else self.table.rowCount()
                checked = [i for i in range(self.table.rowCount()) if self.table.item(i,0).checkState() == Qt.Checked]
                insert_at = checked[0] if checked else insert_at
                for i in range(si, ei+1):
                    self.add_table_row_at(insert_at, f"{s0}.{i}")
                    insert_at += 1
        else:
            try: si=int(start); ei=int(end)
            except: return
            # insert lessons at selected row or end
            insert_at = self.table.currentRow() if self.table.currentRow() >= 0 else self.table.rowCount()
            checked = [i for i in range(self.table.rowCount()) if self.table.item(i,0).checkState() == Qt.Checked]
            insert_at = checked[0] if checked else insert_at
            for i in range(si, ei+1):
                self.add_table_row_at(insert_at, str(i))
                insert_at += 1
        self.table.resizeColumnsToContents()
        # adjust dialog width to fit all sequence table columns
        screen_rect = QApplication.desktop().availableGeometry()
        max_w = int(screen_rect.width() * 0.8)
        table_w = self.table.verticalHeader().width() + sum(self.table.columnWidth(i) for i in range(self.table.columnCount()))
        needed_w = min(table_w + self.table.verticalScrollBar().sizeHint().width() + 20, max_w)
        self.scroll.setMinimumWidth(needed_w)
        self.setMinimumWidth(needed_w + 40)
        self.table.resizeRowsToContents()
        self.adjustSize()

    def add_table_row(self, number):
        # insert one lesson row
        r = self.table.rowCount()
        self.table.insertRow(r)
        # checkbox
        cb_item = QTableWidgetItem()
        cb_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        cb_item.setCheckState(Qt.Unchecked)
        self.table.setItem(r,0,cb_item)
        # lesson fields
        self.table.setItem(r,1,QTableWidgetItem(number))
        self.table.setItem(r,2,QTableWidgetItem(""))
        self.table.setItem(r,3,QTableWidgetItem(""))
        # type dropdown
        type_cb = QComboBox()
        type_cb.addItems(self.type_options)
        type_cb.setEditable(True)
        self.table.setCellWidget(r,4,type_cb)
        # status dropdown
        status_cb = QComboBox()
        status_cb.addItems(self.status_options)
        status_cb.setEditable(True)
        self.table.setCellWidget(r,5,status_cb)
        # review dropdown
        review_cb = QComboBox()
        review_cb.addItems(["Pending","Approved"])
        review_cb.setCurrentIndex(0)
        self.table.setCellWidget(r,6,review_cb)
        # anchor date widget
        anchor_widget = QWidget()
        aw_layout = QHBoxLayout(anchor_widget)
        aw_layout.setContentsMargins(0,0,0,0)
        anchor_cb = QCheckBox()
        anchor_de = QDateEdit(calendarPopup=True)
        anchor_de.setEnabled(False)
        if lesson.anchor_date:
            qd = QDate(lesson.anchor_date.year, lesson.anchor_date.month, lesson.anchor_date.day)
            anchor_cb.setChecked(True)
            anchor_de.setEnabled(True)
            anchor_de.setDate(qd)
        else:
            anchor_cb.setChecked(False)
            anchor_de.setDate(QDate.currentDate())
        anchor_cb.stateChanged.connect(lambda s, de=anchor_de: de.setEnabled(s == Qt.Checked))
        aw_layout.addWidget(anchor_cb)
        aw_layout.addWidget(anchor_de)
        self.table.setCellWidget(r,7,anchor_widget)
        # action buttons
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self.on_edit_button_clicked)
        self.table.setCellWidget(r,8,edit_btn)
        rem_btn = QPushButton("Remove")
        rem_btn.clicked.connect(self.on_remove_button_clicked)
        self.table.setCellWidget(r,9,rem_btn)
        # add reorder buttons
        up_btn = QPushButton("▲")
        up_btn.clicked.connect(self.move_up_clicked)
        self.table.setCellWidget(r,10,up_btn)
        down_btn = QPushButton("▼")
        down_btn.clicked.connect(self.move_down_clicked)
        self.table.setCellWidget(r,11,down_btn)
        self.lesson_ids.append(None)
        # adjust sizes
        self.adjustSize()
        # commit session to make changes immediately available
        try:
            self.session.commit()
            print("Successfully committed new lesson.")
        except Exception as e:
            print(f"Error committing new lesson - {e}")

    def add_table_row_at(self, index, number):
        # insert one lesson row at a specific position
        r = index
        self.table.insertRow(r)
        cb_item = QTableWidgetItem()
        cb_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        cb_item.setCheckState(Qt.Unchecked)
        self.table.setItem(r, 0, cb_item)
        self.table.setItem(r, 1, QTableWidgetItem(number))
        self.table.setItem(r, 2, QTableWidgetItem(""))
        self.table.setItem(r, 3, QTableWidgetItem(""))
        type_cb = QComboBox()
        type_cb.addItems(self.type_options)
        type_cb.setEditable(True)
        self.table.setCellWidget(r, 4, type_cb)
        status_cb = QComboBox()
        status_cb.addItems(self.status_options)
        status_cb.setEditable(True)
        self.table.setCellWidget(r, 5, status_cb)
        review_cb = QComboBox()
        review_cb.addItems(["Pending", "Approved"])
        review_cb.setCurrentIndex(0)
        self.table.setCellWidget(r, 6, review_cb)
        anchor_widget = QWidget()
        aw_layout = QHBoxLayout(anchor_widget)
        aw_layout.setContentsMargins(0, 0, 0, 0)
        anchor_cb = QCheckBox()
        anchor_de = QDateEdit(calendarPopup=True)
        anchor_de.setEnabled(False)
        anchor_cb.stateChanged.connect(lambda s, de=anchor_de: de.setEnabled(s == Qt.Checked))
        aw_layout.addWidget(anchor_cb);
        aw_layout.addWidget(anchor_de)
        self.table.setCellWidget(r, 7, anchor_widget)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self.on_edit_button_clicked)
        self.table.setCellWidget(r, 8, edit_btn)
        rem_btn = QPushButton("Remove")
        rem_btn.clicked.connect(self.on_remove_button_clicked)
        self.table.setCellWidget(r, 9, rem_btn)
        up_btn = QPushButton("▲"); up_btn.clicked.connect(self.move_up_clicked)
        dn_btn = QPushButton("▼"); dn_btn.clicked.connect(self.move_down_clicked)
        self.table.setCellWidget(r, 10, up_btn)
        self.table.setCellWidget(r, 11, dn_btn)
        # create and persist new Lesson immediately
        new_lesson = Lesson(class_subject_id=self.class_subject_id,
                             number=number, name="",
                             learning_objective="",
                             lesson_type=None, status=None,
                             review_status=None, anchor_date=None,
                             sequence=r)
        self.session.add(new_lesson)
        self.session.flush()
        self.lesson_ids.insert(r, new_lesson.id)
        self.adjustSize()
        try:
            self.session.commit()
            print(f"Successfully committed new lesson at row {r}.")
        except Exception as e:
            print(f"Error committing new lesson - {e}")

    def add_single_lesson(self):
        num, ok = QInputDialog.getText(self, "Insert Lesson", "Lesson Number:")
        if ok and num.strip():
            # determine insertion index from checked row or current selection
            checked = [i for i in range(self.table.rowCount()) if self.table.item(i, 0).checkState() == Qt.Checked]
            row = checked[0] if checked else (self.table.currentRow() if self.table.currentRow() >= 0 else self.table.rowCount())
            self.add_table_row_at(row, num.strip())

    def remove_selected_lessons(self):
        rows = [i for i in range(self.table.rowCount()) if self.table.item(i, 0).checkState() == Qt.Checked]
        if not rows:
            return
        reply = QMessageBox.question(self, "Confirm Removal", f"Remove {len(rows)} selected lesson(s)?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        for row in sorted(rows, reverse=True):
            self.table.removeRow(row)
            del self.lesson_ids[row]

    def remove_all_lessons(self):
        count = self.table.rowCount()
        if count == 0:
            return
        reply = QMessageBox.question(self, "Confirm Removal", f"Remove all {count} lessons?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.table.setRowCount(0)
        self.lesson_ids.clear()

    def open_lesson_detail(self, row, col):
        lesson_id = self.lesson_ids[row]
        # if not yet persisted, create new Lesson in DB
        if lesson_id is None:
            # retrieve basic fields from table
            num = self.table.item(row,1).text() if self.table.item(row,1) else ""
            name = self.table.item(row,2).text() if self.table.item(row,2) else ""
            obj = self.table.item(row,3).text() if self.table.item(row,3) else ""
            new_l = Lesson(class_subject_id=self.class_subject_id, number=num, name=name, learning_objective=obj)
            self.session.add(new_l)
            try:
                self.session.commit()
                print("Successfully committed new lesson.")
            except Exception as e:
                print(f"Error committing new lesson - {e}")
            lesson_id = new_l.id
            self.lesson_ids[row] = lesson_id
        dlg = LessonDetailDialog(self, lesson_id)
        res = dlg.exec_()
        if res == QDialog.Accepted:
            # refresh the table row with updated lesson values
            session2 = SessionLocal()
            updated = session2.query(Lesson).filter_by(id=lesson_id).one()
            session2.close()
            # update columns: number, name, objective
            self.table.item(row,1).setText(updated.number)
            self.table.item(row,2).setText(updated.name or "")
            self.table.item(row,3).setText(updated.learning_objective or "")
            # update type
            type_cb = self.table.cellWidget(row,4)
            if isinstance(type_cb, QComboBox):
                t = updated.lesson_type or ""
                idx = type_cb.findText(t)
                if idx >= 0:
                    type_cb.setCurrentIndex(idx)
                else:
                    type_cb.setEditText(t)
            # update status
            status_cb = self.table.cellWidget(row,5)
            if isinstance(status_cb, QComboBox):
                s = updated.status or ""
                idx2 = status_cb.findText(s)
                if idx2 >= 0:
                    status_cb.setCurrentIndex(idx2)
                else:
                    status_cb.setEditText(s)
            # update review
            review_cb = self.table.cellWidget(row,6)
            if isinstance(review_cb, QComboBox):
                r = updated.review_status or ""
                idx3 = review_cb.findText(r)
                if idx3 >= 0:
                    review_cb.setCurrentIndex(idx3)
                else:
                    review_cb.setEditText(r)
            # update anchor date
            aw = self.table.cellWidget(row,7)
            if aw:
                cbx = aw.layout().itemAt(0).widget()
                de = aw.layout().itemAt(1).widget()
                if updated.anchor_date:
                    qd2 = QDate(updated.anchor_date.year, updated.anchor_date.month, updated.anchor_date.day)
                    cbx.setChecked(True)
                    de.setEnabled(True)
                    de.setDate(qd2)
                else:
                    cbx.setChecked(False)
                    de.setEnabled(False)
                    de.setDate(QDate.currentDate())

    def on_edit_button_clicked(self):
        btn = self.sender()
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row,8) == btn:
                self.open_lesson_detail(row, 0)
                break

    def on_remove_button_clicked(self):
        btn = self.sender()
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row,9) == btn:
                num = self.table.item(row,1).text() if self.table.item(row,1) else ""
                reply = QMessageBox.question(self, "Confirm Removal", f"Remove lesson {num}?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.table.removeRow(row)
                    del self.lesson_ids[row]
                    self.table.resizeRowsToContents()
                    self.table.resizeColumnsToContents()
                    self.adjustSize()
                break

    def move_up_clicked(self):
        btn = self.sender()
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row,10) == btn and row > 0:
                self.swap_rows(row, row-1)
                break

    def move_down_clicked(self):
        btn = self.sender()
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row,11) == btn and row < self.table.rowCount()-1:
                self.swap_rows(row, row+1)
                break

    def swap_rows(self, r1, r2):
        # swap IDs in memory
        self.lesson_ids[r1], self.lesson_ids[r2] = self.lesson_ids[r2], self.lesson_ids[r1]
        # persist updated sequence numbers in DB
        for idx, lid in enumerate(self.lesson_ids):
            lesson = self.session.query(Lesson).filter_by(id=lid).one()
            lesson.sequence = idx
        self.session.commit()
        # rebuild table with new order
        self.refresh_sequence_table()
        # scroll to the moved row after the event loop updates sizes
        QTimer.singleShot(0, lambda row=r2: self._scroll_to_row(row))

    def _scroll_to_row(self, row):
        # ensure given row is visible in the scroll area
        if row < 0 or row >= self.table.rowCount():
            return
        row_offset = self.table.rowViewportPosition(row)
        table_y = self.table.pos().y()
        scroll_y = table_y + row_offset
        self.scroll.verticalScrollBar().setValue(scroll_y)

    def refresh_sequence_table(self):
        # repopulate the table rows according to lesson_ids
        lessons = [self.session.query(Lesson).filter_by(id=lid).one() for lid in self.lesson_ids]
        self.table.setRowCount(0)
        for idx, lesson in enumerate(lessons):
            self.table.insertRow(idx)
            # checkbox
            cb = QTableWidgetItem()
            cb.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            cb.setCheckState(Qt.Unchecked)
            self.table.setItem(idx, 0, cb)
            # number, name, objective
            self.table.setItem(idx, 1, QTableWidgetItem(lesson.number))
            self.table.setItem(idx, 2, QTableWidgetItem(lesson.name or ""))
            self.table.setItem(idx, 3, QTableWidgetItem(lesson.learning_objective or ""))
            # type dropdown
            type_cb = QComboBox()
            type_cb.addItems(self.type_options)
            type_cb.setEditable(True)
            if lesson.lesson_type:
                pos = type_cb.findText(lesson.lesson_type)
                if pos >= 0: type_cb.setCurrentIndex(pos)
            self.table.setCellWidget(idx, 4, type_cb)
            # status dropdown
            status_cb = QComboBox()
            status_cb.addItems(self.status_options)
            status_cb.setEditable(True)
            if lesson.status:
                pos = status_cb.findText(lesson.status)
                if pos >= 0: status_cb.setCurrentIndex(pos)
            self.table.setCellWidget(idx, 5, status_cb)
            # review dropdown
            review_cb = QComboBox()
            review_cb.addItems(["Pending", "Approved"])
            if lesson.review_status:
                pos = review_cb.findText(lesson.review_status)
                if pos >= 0: review_cb.setCurrentIndex(pos)
            self.table.setCellWidget(idx, 6, review_cb)
            # anchor date
            w = QWidget()
            lay = QHBoxLayout(w)
            lay.setContentsMargins(0,0,0,0)
            cbx = QCheckBox()
            de = QDateEdit(calendarPopup=True)
            de.setEnabled(False)
            if lesson.anchor_date:
                qd = QDate(lesson.anchor_date.year, lesson.anchor_date.month, lesson.anchor_date.day)
                cbx.setChecked(True)
                de.setEnabled(True)
                de.setDate(qd)
            else:
                cbx.setChecked(False)
                de.setDate(QDate.currentDate())
            cbx.stateChanged.connect(lambda s, d=de: d.setEnabled(s == Qt.Checked))
            lay.addWidget(cbx);
            lay.addWidget(de)
            self.table.setCellWidget(idx, 7, w)
            # edit/remove
            e_btn = QPushButton("Edit")
            e_btn.clicked.connect(self.on_edit_button_clicked)
            self.table.setCellWidget(idx, 8, e_btn)
            r_btn = QPushButton("Remove")
            r_btn.clicked.connect(self.on_remove_button_clicked)
            self.table.setCellWidget(idx, 9, r_btn)
            # up/down
            up = QPushButton("▲"); up.clicked.connect(self.move_up_clicked)
            dn = QPushButton("▼"); dn.clicked.connect(self.move_down_clicked)
            self.table.setCellWidget(idx, 10, up)
            self.table.setCellWidget(idx, 11, dn)
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        self.adjustSize()

    def merge_selected_lessons(self):
        rows = [i for i in range(self.table.rowCount()) if self.table.item(i, 0).checkState() == Qt.Checked]
        if len(rows) != 2:
            QMessageBox.warning(self, "Merge Lessons", "Please select exactly two lessons to merge.")
            return
        r1, r2 = sorted(rows)
        # get lesson IDs and objects
        id1 = self.lesson_ids[r1]
        id2 = self.lesson_ids[r2]
        l1 = self.session.query(Lesson).filter_by(id=id1).one()
        l2 = self.session.query(Lesson).filter_by(id=id2).one()
        # combine key fields
        l1.number = f"{l1.number} & {l2.number}"
        # name
        if l1.name and l2.name:
            l1.name = f"{l1.name} & {l2.name}"
        else:
            l1.name = l1.name or l2.name
        # learning objectives
        if l1.learning_objective and l2.learning_objective:
            l1.learning_objective = f"{l1.learning_objective}\n{l2.learning_objective}"
        else:
            l1.learning_objective = l1.learning_objective or l2.learning_objective
        # combine lesson_type
        if l1.lesson_type and l2.lesson_type:
            l1.lesson_type = f"{l1.lesson_type} & {l2.lesson_type}"
        else:
            l1.lesson_type = l1.lesson_type or l2.lesson_type
        # combine status
        if l1.status and l2.status:
            l1.status = f"{l1.status} & {l2.status}"
        else:
            l1.status = l1.status or l2.status
        # combine review_status
        if l1.review_status and l2.review_status:
            l1.review_status = f"{l1.review_status} & {l2.review_status}"
        else:
            l1.review_status = l1.review_status or l2.review_status
        # combine anchor_date (earliest)
        if l1.anchor_date and l2.anchor_date:
            l1.anchor_date = min(l1.anchor_date, l2.anchor_date)
        else:
            l1.anchor_date = l1.anchor_date or l2.anchor_date
        # combine lesson_plans_notes
        if l1.lesson_plans_notes and l2.lesson_plans_notes:
            l1.lesson_plans_notes = f"{l1.lesson_plans_notes}\n{l2.lesson_plans_notes}"
        else:
            l1.lesson_plans_notes = l1.lesson_plans_notes or l2.lesson_plans_notes
        # combine post_lesson_notes
        if l1.post_lesson_notes and l2.post_lesson_notes:
            l1.post_lesson_notes = f"{l1.post_lesson_notes}\n{l2.post_lesson_notes}"
        else:
            l1.post_lesson_notes = l1.post_lesson_notes or l2.post_lesson_notes
        # combine materials
        mats1 = [m.strip() for m in (l1.materials or "").split(",") if m.strip()]
        mats2 = [m.strip() for m in (l2.materials or "").split(",") if m.strip()]
        combined_mats = ",".join(sorted(set(mats1 + mats2)))
        l1.materials = combined_mats or None
        # combine pdf_paths
        p1 = [p.strip() for p in (l1.pdf_paths or "").split(",") if p.strip()]
        p2 = [p.strip() for p in (l2.pdf_paths or "").split(",") if p.strip()]
        combined_pdfs = ",".join(sorted(set(p1 + p2)))
        l1.pdf_paths = combined_pdfs or None
        # delete second lesson
        self.session.delete(l2)
        self.session.commit()
        # update in-memory list and UI
        del self.lesson_ids[r2]
        self.refresh_sequence_table()

    def _on_sequence_cell_changed(self, row, col):
        # skip if row index is out of range or no lesson ID
        if row < 0 or row >= len(self.lesson_ids):
            return
        lid = self.lesson_ids[row]
        if lid is None:
            return
        if col in (1,2,3):
            l = self.session.query(Lesson).filter_by(id=lid).one()
            val = self.table.item(row, col).text()
            if col == 1:
                l.number = val
            elif col == 2:
                l.name = val
            else:
                l.learning_objective = val
            self.session.commit()

    def _update_sequence_field(self, row, field, value):
        # skip if row index is out of range or no lesson ID
        if row < 0 or row >= len(self.lesson_ids):
            return
        lid = self.lesson_ids[row]
        if lid is None:
            return
        l = self.session.query(Lesson).filter_by(id=lid).one()
        setattr(l, field, value)
        self.session.commit()

    def _update_anchor_date(self, row, state, qdate):
        # skip if row index is out of range or no lesson ID
        if row < 0 or row >= len(self.lesson_ids):
            return
        lid = self.lesson_ids[row]
        if lid is None:
            return
        l = self.session.query(Lesson).filter_by(id=lid).one()
        if state == Qt.Checked:
            l.anchor_date = qdate.toPyDate()
        else:
            l.anchor_date = None
        self.session.commit()

    def save_and_close(self):
        # refresh loaded lessons so detail-dialog edits aren't overwritten
        self.session.expire_all()
        existing = {l.id: l for l in self.session.query(Lesson).filter_by(class_subject_id=self.class_subject_id).all()}
        for r in range(self.table.rowCount()):
            lid = self.lesson_ids[r]
            num = self.table.item(r,1).text() if self.table.item(r,1) else ""
            name = self.table.item(r,2).text() if self.table.item(r,2) else ""
            obj = self.table.item(r,3).text() if self.table.item(r,3) else ""
            lesson_type = self.table.cellWidget(r,4).currentText() if isinstance(self.table.cellWidget(r,4), QComboBox) else None
            status = self.table.cellWidget(r,5).currentText() if isinstance(self.table.cellWidget(r,5), QComboBox) else None
            review = self.table.cellWidget(r,6).currentText() if isinstance(self.table.cellWidget(r,6), QComboBox) else None
            aw = self.table.cellWidget(r,7)
            anchor_cb = aw.layout().itemAt(0).widget() if aw else None
            anchor_de = aw.layout().itemAt(1).widget() if aw else None
            anchor_date = anchor_de.date().toPyDate() if anchor_cb and anchor_cb.isChecked() else None
            if lid in existing:
                lesson = existing.pop(lid)
                lesson.number = num
                lesson.name = name
                lesson.learning_objective = obj
                lesson.lesson_type = lesson_type
                lesson.status = status
                lesson.review_status = review
                lesson.anchor_date = anchor_date
                lesson.sequence = r
            else:
                new_lesson = Lesson(class_subject_id=self.class_subject_id,
                                     number=num, name=name,
                                     learning_objective=obj,
                                     lesson_type=lesson_type, status=status,
                                     review_status=review, anchor_date=anchor_date,
                                     sequence=r)
                self.session.add(new_lesson)
                self.session.flush()
                self.lesson_ids[r] = new_lesson.id
        # delete removed lessons
        for l in existing.values():
            self.session.delete(l)
        try:
            self.session.commit()
            print("Successfully synchronized lessons.")
        except Exception as e:
            print(f"Error synchronizing lessons - {e}")
        self.session.close()
        self.accept()
