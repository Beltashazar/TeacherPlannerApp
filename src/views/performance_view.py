from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QComboBox, QListWidget, QListWidgetItem, QPushButton, QTextEdit
from PyQt5.QtCore import Qt
from database import SessionLocal
from models import ClassSubject, RosterEntry, Lesson, LessonPerformance

class PerformanceView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session = SessionLocal()
        # Class selector
        class_layout = QHBoxLayout()
        class_layout.addWidget(QLabel("Class:"))
        self.class_combo = QComboBox()
        class_layout.addWidget(self.class_combo)
        self.class_combo.currentIndexChanged.connect(self.on_class_changed)
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(class_layout)
        # Content split: students list vs stats/detail
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)
        # Student list
        self.student_list = QListWidget()
        self.student_list.currentItemChanged.connect(self.on_student_selected)
        content_layout.addWidget(self.student_list)
        # Right panel for stats
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        content_layout.addWidget(right_panel)
        # Class-level stats
        self.class_group = QGroupBox("Class Performance Summary")
        cls_form = QFormLayout()
        self.avg_green_label = QLabel()
        self.avg_yellow_label = QLabel()
        self.avg_red_label = QLabel()
        cls_form.addRow("Avg Greens/Lesson:", self.avg_green_label)
        cls_form.addRow("Avg Yellows/Lesson:", self.avg_yellow_label)
        cls_form.addRow("Avg Reds/Lesson:", self.avg_red_label)
        self.class_group.setLayout(cls_form)
        right_layout.addWidget(self.class_group)
        # Student detail (hidden until selection)
        self.student_group = QGroupBox("Student Performance Detail")
        stu_layout = QHBoxLayout()
        self.lesson_list = QListWidget()
        self.lesson_list.currentItemChanged.connect(self.on_lesson_selected)
        stu_layout.addWidget(self.lesson_list)
        # Student stats
        stu_stat_group = QGroupBox("Student Summary")
        stu_stat_form = QFormLayout()
        self.stu_avg_green = QLabel()
        self.stu_avg_yellow = QLabel()
        self.stu_avg_red = QLabel()
        stu_stat_form.addRow("Avg Greens/Lesson:", self.stu_avg_green)
        stu_stat_form.addRow("Avg Yellows/Lesson:", self.stu_avg_yellow)
        stu_stat_form.addRow("Avg Reds/Lesson:", self.stu_avg_red)
        stu_stat_group.setLayout(stu_stat_form)
        stu_layout.addWidget(stu_stat_group)
        self.student_group.setLayout(stu_layout)
        right_layout.addWidget(self.student_group)
        # Lesson edit panel
        self.lesson_edit_group = QGroupBox("Edit Lesson Performance")
        edit_form = QFormLayout()
        self.status_edit = QComboBox()
        self.status_edit.addItems(["Green", "Yellow", "Red"])
        edit_form.addRow("Status:", self.status_edit)
        self.feedback_edit = QTextEdit()
        edit_form.addRow("Feedback:", self.feedback_edit)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_performance)
        edit_form.addRow(self.save_button)
        self.lesson_edit_group.setLayout(edit_form)
        right_layout.addWidget(self.lesson_edit_group)
        self.student_group.hide()
        self.lesson_edit_group.hide()
        # Populate classes
        self.load_classes()

    def load_classes(self):
        classes = self.session.query(ClassSubject).order_by(ClassSubject.name).all()
        self.class_combo.clear()
        for cs in classes:
            self.class_combo.addItem(cs.name, cs.id)

    def on_class_changed(self, index):
        class_id = self.class_combo.itemData(index)
        if class_id is None:
            return
        # Lessons for class
        lessons = self.session.query(Lesson).filter_by(class_subject_id=class_id).order_by(Lesson.sequence).all()
        lesson_ids = [l.id for l in lessons]
        lessons_count = len(lesson_ids)
        # Class-level statistics
        if lessons_count:
            green_count = self.session.query(LessonPerformance).filter(LessonPerformance.lesson_id.in_(lesson_ids), LessonPerformance.status=="Green").count()
            yellow_count = self.session.query(LessonPerformance).filter(LessonPerformance.lesson_id.in_(lesson_ids), LessonPerformance.status=="Yellow").count()
            red_count = self.session.query(LessonPerformance).filter(LessonPerformance.lesson_id.in_(lesson_ids), LessonPerformance.status=="Red").count()
            self.avg_green_label.setText(f"{green_count/lessons_count:.2f}")
            self.avg_yellow_label.setText(f"{yellow_count/lessons_count:.2f}")
            self.avg_red_label.setText(f"{red_count/lessons_count:.2f}")
        else:
            self.avg_green_label.setText("0")
            self.avg_yellow_label.setText("0")
            self.avg_red_label.setText("0")
        # Populate students list
        students = self.session.query(RosterEntry).filter_by(class_subject_id=class_id).order_by(RosterEntry.name).all()
        self.student_list.clear()
        for r in students:
            item = QListWidgetItem(r.name)
            item.setData(Qt.UserRole, r.id)
            self.student_list.addItem(item)
        self.student_group.hide()

    def on_student_selected(self, current, previous):
        if not current:
            self.student_group.hide()
            return
        self.current_student_id = current.data(Qt.UserRole)
        class_id = self.class_combo.currentData()
        if class_id is None:
            return
        # Fetch lessons
        lessons = self.session.query(Lesson).filter_by(class_subject_id=class_id).order_by(Lesson.sequence).all()
        lesson_ids = [l.id for l in lessons]
        lessons_count = len(lesson_ids)
        # Populate lesson list with status and notes
        self.lesson_list.clear()
        for l in lessons:
            perf = self.session.query(LessonPerformance).filter_by(lesson_id=l.id, roster_entry_id=self.current_student_id).first()
            status = perf.status if perf and perf.status else "N/A"
            notes = perf.notes if perf and perf.notes else ""
            item = QListWidgetItem(f"{l.number}: {status} - {notes}")
            item.setData(Qt.UserRole, l.id)
            self.lesson_list.addItem(item)
        # Student-level stats
        if lessons_count:
            green_c = self.session.query(LessonPerformance).filter(LessonPerformance.roster_entry_id==self.current_student_id, LessonPerformance.lesson_id.in_(lesson_ids), LessonPerformance.status=="Green").count()
            yellow_c = self.session.query(LessonPerformance).filter(LessonPerformance.roster_entry_id==self.current_student_id, LessonPerformance.lesson_id.in_(lesson_ids), LessonPerformance.status=="Yellow").count()
            red_c = self.session.query(LessonPerformance).filter(LessonPerformance.roster_entry_id==self.current_student_id, LessonPerformance.lesson_id.in_(lesson_ids), LessonPerformance.status=="Red").count()
            self.stu_avg_green.setText(f"{green_c/lessons_count:.2f}")
            self.stu_avg_yellow.setText(f"{yellow_c/lessons_count:.2f}")
            self.stu_avg_red.setText(f"{red_c/lessons_count:.2f}")
        else:
            self.stu_avg_green.setText("0")
            self.stu_avg_yellow.setText("0")
            self.stu_avg_red.setText("0")
        self.student_group.show()

    def on_lesson_selected(self, current, previous):
        if not current:
            self.lesson_edit_group.hide()
            return
        lesson_id = current.data(Qt.UserRole)
        student_id = self.current_student_id
        perf = self.session.query(LessonPerformance).filter_by(lesson_id=lesson_id, roster_entry_id=student_id).first()
        if not perf:
            perf = LessonPerformance(lesson_id=lesson_id, roster_entry_id=student_id, status="Green", notes="")
            self.session.add(perf)
            self.session.commit()
        self.current_perf = perf
        self.status_edit.setCurrentText(perf.status)
        self.feedback_edit.setPlainText(perf.notes)
        self.lesson_edit_group.show()

    def save_performance(self):
        perf = self.current_perf
        perf.status = self.status_edit.currentText()
        perf.notes = self.feedback_edit.toPlainText()
        self.session.commit()
        # update lesson_list item text
        lesson = self.session.query(Lesson).filter_by(id=perf.lesson_id).first()
        for idx in range(self.lesson_list.count()):
            item = self.lesson_list.item(idx)
            if item.data(Qt.UserRole) == perf.lesson_id:
                item.setText(f"{lesson.number}: {perf.status} - {perf.notes}")
                break
        # refresh student stats
        self.on_student_selected(self.student_list.currentItem(), None)
