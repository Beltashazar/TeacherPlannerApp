from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QScrollArea, QWidget, QFrame)
from PyQt5.QtCore import Qt
from database import SessionLocal
from models import Lesson, ClassSubject
from datetime import date, timedelta

class WeeklyViewDialog(QDialog):
    def __init__(self, parent, class_subject_id):
        super().__init__(parent)
        self.class_subject_id = class_subject_id
        self.session = SessionLocal()

        subj = self.session.query(ClassSubject).filter_by(id=class_subject_id).first()
        title = f"Weekly View - {subj.name}" + (f" ({subj.section})" if subj and subj.section else "")
        self.setWindowTitle(title)

        # calculate current week's Monday
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        dates = [monday + timedelta(days=i) for i in range(7)]
        day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

        layout = QVBoxLayout(self)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll)

        content = QWidget()
        self.scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        
        for dn, dt in zip(day_names, dates):
            gb = QGroupBox(f"{dn} ({dt.isoformat()})")
            gb_layout = QHBoxLayout()
            lessons = self.session.query(Lesson).filter_by(class_subject_id=class_subject_id, anchor_date=dt).all()
            if not lessons:
                lbl = QLabel("No lessons")
                lbl.setStyleSheet("color: gray;")
                gb_layout.addWidget(lbl)
            for les in lessons:
                card = QFrame()
                card.setFrameShape(QFrame.StyledPanel)
                card.setLineWidth(1)
                card_layout = QVBoxLayout(card)
                # elide utility
                def elide(text, length=50):
                    if not text:
                        return ""
                    return text if len(text) <= length else text[:length] + "…"
                card_layout.addWidget(QLabel(f"<b>#{elide(les.number,10)}</b> {elide(les.name or '',20)}"))
                card_layout.addWidget(QLabel(f"Obj: {elide(les.learning_objective or '',50)}"))
                card_layout.addWidget(QLabel(f"Plans: {elide(les.lesson_plans_notes or '',50)}"))
                card_layout.addWidget(QLabel(f"Post: {elide(les.post_lesson_notes or '',50)}"))
                card_layout.addWidget(QLabel(f"Mats: {elide(les.materials or '',30)}"))
                pdfs = [p for p in (les.pdf_paths or "").split(",") if p]
                if pdfs:
                    card_layout.addWidget(QLabel(f"PDFs: {len(pdfs)}"))
                gb_layout.addWidget(card)
            gb.setLayout(gb_layout)
            content_layout.addWidget(gb)
        
        self.resize(800, 600)
