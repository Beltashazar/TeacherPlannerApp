from setuptools import setup

APP = ['src/main.py']
DATA_FILES = ['data/planner.db']
OPTIONS = {
    'argv_emulation': True,
    'includes': ['PyQt5'],
    'packages': ['views', 'models'],
    # 'iconfile': 'resources/TeacherPlanner.icns',  # optional custom icon
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
