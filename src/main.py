import sys
from PyQt5.QtWidgets import QApplication
from gui import MainWindow

__version__ = '1.0.0'

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
