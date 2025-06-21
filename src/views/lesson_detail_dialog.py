from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QScrollArea, QWidget, QFormLayout, QComboBox, QCheckBox, QDateEdit, QLineEdit, QLabel, QPushButton, QTextEdit, QListWidget, QListWidgetItem, QDialogButtonBox, QMessageBox, QLayout, QApplication, QGroupBox, QHBoxLayout, QGridLayout, QSizePolicy, QFileDialog, QInputDialog)
from PyQt5.QtCore import Qt, QDate, QUrl
from PyQt5.QtGui import QDesktopServices, QFont, QTextListFormat
import os
from functools import partial
import shutil
from database import SessionLocal
from models import Lesson, LessonPerformance, RosterEntry, ClassSubject, MaterialNeeded

class LessonDetailDialog(QDialog):
    def __init__(self, parent, lesson_id):
        super().__init__(parent)
        self.lesson_id = lesson_id
        self.session = SessionLocal()
        lesson = self.session.query(Lesson).filter_by(id=lesson_id).first()
        perf_list = self.session.query(LessonPerformance).filter_by(lesson_id=lesson_id).all()
        # set up storage folder for lesson PDFs
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lesson_pdfs', f'lesson_{lesson_id}'))
        os.makedirs(base_dir, exist_ok=True)
        self.pdf_base_dir = base_dir
        # set window title to include subject name
        subj = self.session.query(ClassSubject).filter_by(id=lesson.class_subject_id).first()
        if subj:
            subj_text = subj.name
            if subj.section:
                subj_text += f" ({subj.section})"
            self.setWindowTitle(f"{subj_text} - Lesson Details")
        else:
            self.setWindowTitle("Lesson Details")
        # main layout and scrollable content area
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        content_widget = QWidget()
        self.scroll.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSizeConstraint(QLayout.SetMinimumSize)
        # limit dialog height: scroll to max 80% of screen
        screen_rect = QApplication.desktop().availableGeometry()
        self.scroll.setMaximumHeight(int(screen_rect.height() * 0.8))
        # Lesson Details
        details_gb = QGroupBox("Lesson Details")
        details_layout = QFormLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Core","Non-Core","Practice","Assessment"])
        if lesson.lesson_type:
            idx = self.type_combo.findText(lesson.lesson_type)
            if idx >= 0: self.type_combo.setCurrentIndex(idx)
        details_layout.addRow("Type:", self.type_combo)
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Not complete","Complete","Skipped"])
        if lesson.status:
            idx = self.status_combo.findText(lesson.status)
            if idx >= 0: self.status_combo.setCurrentIndex(idx)
        details_layout.addRow("Status:", self.status_combo)
        self.review_combo = QComboBox()
        self.review_combo.addItems(["Pending","Approved"])
        if lesson.review_status:
            idx = self.review_combo.findText(lesson.review_status)
            if idx >= 0: self.review_combo.setCurrentIndex(idx)
        details_layout.addRow("Review Status:", self.review_combo)
        anchor_widget = QWidget()
        aw_layout = QHBoxLayout(anchor_widget)
        self.anchor_checkbox = QCheckBox("Anchor Date")
        self.anchor_date_edit = QDateEdit(calendarPopup=True)
        self.anchor_date_edit.setEnabled(False)
        if lesson.anchor_date:
            qd = QDate(lesson.anchor_date.year, lesson.anchor_date.month, lesson.anchor_date.day)
            self.anchor_checkbox.setChecked(True)
            self.anchor_date_edit.setEnabled(True)
            self.anchor_date_edit.setDate(qd)
        else:
            self.anchor_checkbox.setChecked(False)
            self.anchor_date_edit.setDate(QDate.currentDate())
        self.anchor_checkbox.stateChanged.connect(lambda s: self.anchor_date_edit.setEnabled(s == Qt.Checked))
        aw_layout.addWidget(self.anchor_checkbox)
        aw_layout.addWidget(self.anchor_date_edit)
        details_layout.addRow("Anchor Date:", anchor_widget)
        self.number_edit = QLineEdit(lesson.number or "")
        details_layout.addRow("Lesson Number:", self.number_edit)
        self.name_edit = QLineEdit(lesson.name or "")
        details_layout.addRow("Lesson Name:", self.name_edit)
        # single-line objective
        self.objective_edit = QLineEdit(lesson.learning_objective or "")
        details_layout.addRow("Lesson Objective:", self.objective_edit)
        # formatting toolbar for Plans/Notes
        plan_tb = QHBoxLayout()
        for lbl, func in [("B", self.toggle_bold), ("I", self.toggle_italic), ("U", self.toggle_underline), ("•", self.insert_bullet)]:
            btn = QPushButton(lbl)
            btn.setFixedWidth(24)
            btn.clicked.connect(lambda ch, f=func: f(self.plans_edit))
            plan_tb.addWidget(btn)
        details_layout.addRow(plan_tb)
        self.plans_edit = QTextEdit()
        self.plans_edit.setAcceptRichText(True)
        self.plans_edit.setHtml(lesson.lesson_plans_notes or "")
        hint = self.plans_edit.sizeHint()
        self.plans_edit.setMinimumSize(hint.width()*2, hint.height()*2)
        details_layout.addRow("Plans/Notes:", self.plans_edit)
        # formatting toolbar for Post Notes
        post_tb = QHBoxLayout()
        for lbl, func in [("B", self.toggle_bold), ("I", self.toggle_italic), ("U", self.toggle_underline), ("•", self.insert_bullet)]:
            btn = QPushButton(lbl)
            btn.setFixedWidth(24)
            btn.clicked.connect(lambda ch, f=func: f(self.post_edit))
            post_tb.addWidget(btn)
        details_layout.addRow(post_tb)
        self.post_edit = QTextEdit()
        self.post_edit.setAcceptRichText(True)
        self.post_edit.setHtml(lesson.post_lesson_notes or "")
        hint2 = self.post_edit.sizeHint()
        self.post_edit.setMinimumSize(hint2.width()*2, hint2.height()*2)
        details_layout.addRow("Post Notes:", self.post_edit)
        # Materials Needed group
        self.materials_gb = QGroupBox("Materials Needed")
        self.materials_layout = QVBoxLayout()
        self.materials_gb.setLayout(self.materials_layout)
        add_btn = QPushButton("Add Material")
        add_btn.clicked.connect(self.add_material)
        self.materials_layout.addWidget(add_btn)
        # load existing materials
        for m in self.session.query(MaterialNeeded).filter_by(lesson_id=self.lesson_id).all():
            self._add_material_row(m)
        details_layout.addRow(self.materials_gb)
        # Attachments
        self.pdf_list = QListWidget()
        for p in (lesson.pdf_paths or "").split(","):
            if p:
                display = p if p.startswith(("http://","https://")) else os.path.basename(p)
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, p)
                self.pdf_list.addItem(item)
        self.pdf_list.itemDoubleClicked.connect(self.open_attachment)
        pdf_btn = QPushButton("Add File(s)")
        pdf_btn.clicked.connect(self.add_pdfs)
        add_link_btn = QPushButton("Add Link")
        add_link_btn.clicked.connect(self.add_link)
        remove_pdf_btn = QPushButton("Remove Selected File(s)")
        remove_pdf_btn.clicked.connect(self.remove_pdfs)
        btns_hbox = QHBoxLayout()
        btns_hbox.addWidget(pdf_btn)
        btns_hbox.addWidget(add_link_btn)
        btns_hbox.addWidget(remove_pdf_btn)
        details_layout.addRow("Attachments:", self.pdf_list)
        details_layout.addRow("", btns_hbox)
        details_gb.setLayout(details_layout)
        # Student Performance
        perf_gb = QGroupBox("Student Performance")
        perf_layout = QGridLayout()
        perf_layout.setSpacing(4)
        perf_layout.setContentsMargins(2,2,2,2)
        self.perf_widgets = []
        entries = self.session.query(RosterEntry).filter_by(class_subject_id=lesson.class_subject_id).all()
        for idx, r in enumerate(entries):
            btn = QPushButton(r.name)
            btn.setFlat(True)
            btn._status = ""
            btn.clicked.connect(partial(self.cycle_status, btn))
            note_le = QTextEdit()
            note_le.setPlaceholderText("Notes")
            note_le.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            # give a default min height (e.g., two lines) so empty fields are visible
            fm = note_le.fontMetrics()
            default_h = fm.height() * 2 + note_le.frameWidth()*2 + 6
            note_le.setMinimumHeight(default_h)
            def adjust(te=note_le, default_h=default_h):
                doc_h = te.document().documentLayout().documentSize().height()
                desired = int(doc_h + te.frameWidth()*2 + 4)
                te.setFixedHeight(max(desired, default_h))
            note_le.textChanged.connect(adjust)
            adjust()
            p = next((p for p in perf_list if p.roster_entry_id==r.id), None)
            if p:
                btn._status = p.status or ""
                if btn._status:
                    btn.setStyleSheet(f"color: {btn._status.lower()};")
                note_le.setPlainText(p.notes or "")
            perf_layout.addWidget(btn, idx, 0)
            perf_layout.addWidget(note_le, idx, 1)
            self.perf_widgets.append((r.id, btn, note_le))
        perf_gb.setLayout(perf_layout)
        # place details and student performance side by side
        top_hbox = QHBoxLayout()
        top_hbox.addWidget(details_gb)
        top_hbox.addWidget(perf_gb)
        content_layout.addLayout(top_hbox)
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_and_close)
        buttons.rejected.connect(self.reject)
        content_layout.addWidget(buttons)
        layout.addWidget(self.scroll)
        layout.addWidget(buttons)
        # adjust dialog width to fit lesson details & performance side-by-side
        screen_rect = QApplication.desktop().availableGeometry()
        max_w = int(screen_rect.width() * 0.8)
        content_w = content_widget.sizeHint().width()
        needed_w = min(content_w + self.scroll.verticalScrollBar().sizeHint().width() + 20, max_w)
        self.scroll.setMinimumWidth(needed_w)
        self.setMinimumWidth(needed_w + 40)
        self.adjustSize()
        # Resize dialog to 80% of screen dimensions
        screen = QApplication.desktop().availableGeometry()
        width = int(screen.width() * 0.8)
        height = int(screen.height() * 0.8)
        self.resize(width, height)
        # Center dialog on screen
        geom = self.frameGeometry()
        cp = QApplication.desktop().availableGeometry().center()
        geom.moveCenter(cp)
        self.move(geom.topLeft())

    def cycle_status(self, btn):
        seq = ["", "Green", "Yellow", "Red"]
        idx = seq.index(btn._status)
        idx = (idx + 1) % len(seq)
        btn._status = seq[idx]
        if btn._status:
            btn.setStyleSheet(f"color: {btn._status.lower()};")
        else:
            btn.setStyleSheet("")

    def save_and_close(self):
        lesson = self.session.query(Lesson).filter_by(id=self.lesson_id).first()
        lesson.number = self.number_edit.text()
        lesson.name = self.name_edit.text()
        lesson.learning_objective = self.objective_edit.text()
        lesson.lesson_plans_notes = self.plans_edit.toHtml()
        lesson.post_lesson_notes = self.post_edit.toHtml()
        # save type/status/review/anchor
        lesson.lesson_type = self.type_combo.currentText()
        lesson.status = self.status_combo.currentText()
        lesson.review_status = self.review_combo.currentText()
        lesson.anchor_date = self.anchor_date_edit.date().toPyDate() if self.anchor_checkbox.isChecked() else None
        # save PDF attachments
        lesson.pdf_paths = ",".join(self.pdf_list.item(i).data(Qt.UserRole) for i in range(self.pdf_list.count()))
        self.session.commit()
        # save performance
        self.session.query(LessonPerformance).filter_by(lesson_id=self.lesson_id).delete()
        for rid, cb, le in self.perf_widgets:
            status = cb._status
            notes = le.toPlainText()
            if status or notes:
                lp = LessonPerformance(lesson_id=self.lesson_id, roster_entry_id=rid, status=status, notes=notes)
                self.session.add(lp)
        self.session.commit()
        self.session.close()
        self.accept()

    def add_pdfs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", "All Files (*)")
        for f in files:
            if not any(self.pdf_list.item(i).data(Qt.UserRole) == f for i in range(self.pdf_list.count())):
                # copy file to lesson PDF folder
                dest = os.path.join(self.pdf_base_dir, os.path.basename(f))
                try:
                    shutil.copy2(f, dest)
                except Exception as e:
                    QMessageBox.warning(self, "Copy Error", f"Failed to copy {f}: {e}")
                    continue
                display = os.path.basename(dest)
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, dest)
                self.pdf_list.addItem(item)

    def remove_pdfs(self):
        for item in self.pdf_list.selectedItems():
            self.pdf_list.takeItem(self.pdf_list.row(item))

    def toggle_bold(self, edit):
        cursor = edit.textCursor()
        fmt = cursor.charFormat()
        fmt.setFontWeight(QFont.Normal if fmt.fontWeight()==QFont.Bold else QFont.Bold)
        cursor.mergeCharFormat(fmt)
        edit.mergeCurrentCharFormat(fmt)

    def toggle_italic(self, edit):
        cursor = edit.textCursor()
        fmt = cursor.charFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        cursor.mergeCharFormat(fmt)
        edit.mergeCurrentCharFormat(fmt)

    def toggle_underline(self, edit):
        cursor = edit.textCursor()
        fmt = cursor.charFormat()
        fmt.setFontUnderline(not fmt.fontUnderline())
        cursor.mergeCharFormat(fmt)
        edit.mergeCurrentCharFormat(fmt)

    def insert_bullet(self, edit):
        cursor = edit.textCursor()
        list_fmt = QTextListFormat()
        list_fmt.setStyle(QTextListFormat.ListDisc)
        cursor.createList(list_fmt)

    def add_link(self):
        url, ok = QInputDialog.getText(self, "Add Link", "Enter URL:")
        if ok and url:
            # avoid duplicates
            if not any(self.pdf_list.item(i).data(Qt.UserRole) == url for i in range(self.pdf_list.count())):
                display = QUrl(url).fileName() or url
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, url)
                self.pdf_list.addItem(item)

    def open_attachment(self, item):
        text = item.data(Qt.UserRole)
        if text.startswith(("http://", "https://")):
            QDesktopServices.openUrl(QUrl(text))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(text))

    def add_material(self):
        dlg = QDialog(self)
        form = QFormLayout(dlg)
        desc_edit = QLineEdit()
        date_edit = QDateEdit(calendarPopup=True)
        date_edit.setDate(QDate.currentDate())
        form.addRow("Description:", desc_edit)
        form.addRow("Reminder Date:", date_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        form.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec_() == QDialog.Accepted:
            desc = desc_edit.text().strip()
            rem_date = date_edit.date().toPyDate()
            if desc:
                m = MaterialNeeded(lesson_id=self.lesson_id, description=desc, reminder_date=rem_date)
                self.session.add(m)
                self.session.commit()
                self._add_material_row(m)

    def _add_material_row(self, m):
        row = QWidget()
        h = QHBoxLayout(row)
        cb = QCheckBox()
        cb.setChecked(m.acquired)
        lbl = QLabel(m.description)
        date_edit = QDateEdit(calendarPopup=True)
        date_edit.setDate(QDate(m.reminder_date.year, m.reminder_date.month, m.reminder_date.day))
        date_edit.dateChanged.connect(lambda d, _m=m: self._update_reminder_date(_m, d))
        # connect checkbox after lbl and date_edit exist
        cb.stateChanged.connect(lambda s, _m=m, _lbl=lbl, _date_edit=date_edit: self._toggle_acquired(_m, _lbl, _date_edit, s))
        h.addWidget(cb)
        h.addWidget(lbl)
        h.addWidget(date_edit)
        rm = QPushButton("Remove")
        rm.clicked.connect(lambda ch, _m=m, _row=row: self._remove_material(_m, _row))
        h.addWidget(rm)
        self.materials_layout.addWidget(row)
        # style acquired items but keep visible
        if m.acquired:
            lbl.setStyleSheet('text-decoration: line-through; color: gray;')
            date_edit.setEnabled(False)

    def _update_reminder_date(self, m, qdate):
        m.reminder_date = qdate.toPyDate()
        self.session.commit()

    def _toggle_acquired(self, m, lbl, date_edit, state):
        m.acquired = (state == Qt.Checked)
        self.session.commit()
        if m.acquired:
            # strikethrough and disable reminder
            lbl.setStyleSheet('text-decoration: line-through; color: gray;')
            date_edit.setEnabled(False)
        else:
            lbl.setStyleSheet('')
            date_edit.setEnabled(True)

    def _remove_material(self, m, row):
        self.session.delete(m)
        self.session.commit()
        row.setParent(None)
