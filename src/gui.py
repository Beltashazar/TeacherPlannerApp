from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QAction, QMessageBox, QFileDialog
from views.calendar_view import CalendarView
from views.weekly_view import WeeklyView
from views.daily_view import DailyView
from views.config_view import ConfigView
from views.performance_view import PerformanceView
import shutil
from database import db_file, engine, Base

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Teacher Planner")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Navigation buttons
        self.config_button = QPushButton("Configuration")
        self.calendar_button = QPushButton("Calendar View")
        self.weekly_button = QPushButton("Weekly View")
        self.daily_button = QPushButton("Daily View")
        self.performance_button = QPushButton("Performance Dashboard")


        self.calendar_button.clicked.connect(self.show_calendar)
        self.weekly_button.clicked.connect(self.show_weekly)
        self.daily_button.clicked.connect(self.show_daily)
        self.performance_button.clicked.connect(self.show_performance)
        self.config_button.clicked.connect(self.show_config)

        nav_layout = QHBoxLayout()
        nav_layout.addWidget(self.config_button)
        nav_layout.addWidget(self.calendar_button)
        nav_layout.addWidget(self.weekly_button)
        nav_layout.addWidget(self.daily_button)
        nav_layout.addWidget(self.performance_button)

        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(nav_layout)

        self.view_placeholder = QWidget()
        self.main_layout.addWidget(self.view_placeholder)

        self.central_widget.setLayout(self.main_layout)

        # File menu: New Plan Book
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        save_action = QAction("Save Plan Book As...", self)
        save_action.triggered.connect(self.save_plan_book)
        file_menu.addAction(save_action)
        load_action = QAction("Load Plan Book...", self)
        load_action.triggered.connect(self.load_plan_book)
        file_menu.addAction(load_action)
        file_menu.addSeparator()
        new_action = QAction("New Plan Book", self)
        new_action.triggered.connect(self.new_plan_book)
        file_menu.addAction(new_action)

        # Show default view
        self.show_config()

    def clear_placeholder(self):
        if self.view_placeholder:
            self.main_layout.removeWidget(self.view_placeholder)
            self.view_placeholder.deleteLater()

    def show_calendar(self):
        self.clear_placeholder()
        self.view_placeholder = CalendarView()
        self.main_layout.addWidget(self.view_placeholder)

    def show_weekly(self):
        self.clear_placeholder()
        self.weekly_view = WeeklyView()
        # WeeklyView has no lesson_selected signal
        self.view_placeholder = self.weekly_view
        self.main_layout.addWidget(self.view_placeholder)

    def show_daily(self):
        self.clear_placeholder()
        self.view_placeholder = DailyView()
        self.main_layout.addWidget(self.view_placeholder)

    def show_daily_from_weekly(self, subject, date):
        self.clear_placeholder()
        self.view_placeholder = DailyView(subject=subject, date=date)
        self.main_layout.addWidget(self.view_placeholder)

    def show_config(self):
        self.clear_placeholder()
        self.view_placeholder = ConfigView()
        self.main_layout.addWidget(self.view_placeholder)

    def show_performance(self):
        self.clear_placeholder()
        self.view_placeholder = PerformanceView()
        self.main_layout.addWidget(self.view_placeholder)

    def new_plan_book(self):
        # prompt to save before wiping data
        save_resp = QMessageBox.question(self, "Save Plan Book", "Save current plan book before creating new?", QMessageBox.Yes|QMessageBox.No)
        if save_resp == QMessageBox.Yes:
            self.save_plan_book()
        resp = QMessageBox.question(self, "New Plan Book", "This will clear all existing data. Continue?", QMessageBox.Yes|QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        from database import engine, Base
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        QMessageBox.information(self, "New Plan Book", "New plan book created.")
        self.show_config()

    def save_plan_book(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Plan Book As", "", "DB Files (*.db);;All Files (*)")
        if not fname:
            return
        try:
            shutil.copy(db_file, fname)
            QMessageBox.information(self, "Save Plan Book", f"Plan book saved to {fname}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save: {e}")

    def load_plan_book(self):
        # prompt to save current plan book before loading
        save_resp = QMessageBox.question(self, "Save Plan Book", "Save current plan book before loading new?", QMessageBox.Yes|QMessageBox.No)
        if save_resp == QMessageBox.Yes:
            self.save_plan_book()
        fname, _ = QFileDialog.getOpenFileName(self, "Load Plan Book", "", "DB Files (*.db);;All Files (*)")
        if not fname:
            return
        resp = QMessageBox.question(self, "Load Plan Book", "This will replace the current plan book. Continue?", QMessageBox.Yes|QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        try:
            engine.dispose()
            shutil.copy(fname, db_file)
            QMessageBox.information(self, "Load Plan Book", "Plan book loaded and refreshed.")
            # refresh view to reflect loaded plan book
            self.clear_placeholder()
            self.show_config()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load: {e}")
