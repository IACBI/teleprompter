# PyInstaller specification for a single-file Windows build.
#
#     pyinstaller packaging/teleprompter.spec
#
# PySide6 ships far more than this application uses. Excluding the modules below
# takes the bundle from roughly 250 MB to well under 100 MB without touching a
# single feature the app actually calls.

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH).parent
ICON_FILE = PROJECT_ROOT / "packaging" / "teleprompter.ico"

EXCLUDED_QT = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
]

EXCLUDED_OTHER = [
    "tkinter",
    "unittest",
    "pydoc_data",
    "test",
    "matplotlib",
    "scipy",
    "PIL",
    "IPython",
]

a = Analysis(
    [str(PROJECT_ROOT / "src" / "teleprompter" / "__main__.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[],
    # QtSvg draws the icon set; QtPrintSupport is unused (export goes through
    # QPdfWriter in QtGui), so only the essentials are pulled in explicitly.
    hiddenimports=collect_submodules("teleprompter") + ["PySide6.QtSvg"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDED_QT + EXCLUDED_OTHER,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TelePrompter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # No console: unhandled errors go to the rotating log file and the crash
    # dialog, which is exactly why that machinery exists.
    console=False,
    disable_windowed_traceback=False,
    icon=str(ICON_FILE) if ICON_FILE.exists() else None,
)
