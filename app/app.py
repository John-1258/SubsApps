import os
import sys
from pathlib import Path

# -----------------------------
# 1) Make stdout/stderr safe (windowed exe has no console on some PCs)
# -----------------------------
def _ensure_stdio():
    try:
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w")
    except Exception:
        pass

_ensure_stdio()

# -----------------------------
# 2) Make FFmpeg available (works for PyInstaller onefile)
# -----------------------------
def _setup_ffmpeg_path():
    """
    Ensure 'ffmpeg.exe' (and optionally ffprobe.exe) can be found by subprocess calls.

    PyInstaller onefile extracts files to sys._MEIPASS at runtime.
    We add that folder's ffmpeg/ to PATH so calls like 'ffmpeg ...' work.
    """
    try:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base = Path(sys._MEIPASS)  # runtime extraction dir
        else:
            # running from source: project root is 2 levels up from this file (app/app.py)
            base = Path(__file__).resolve().parents[1]

        ffmpeg_dir = base / "ffmpeg"
        ffmpeg_exe = ffmpeg_dir / "ffmpeg.exe"
        ffprobe_exe = ffmpeg_dir / "ffprobe.exe"

        # If you bundled into ffmpeg/ffmpeg.exe, it must exist here
        if ffmpeg_exe.exists():
            os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")
            # Some libraries also respect this:
            os.environ["FFMPEG_BINARY"] = str(ffmpeg_exe)
        # Not mandatory, but useful if your stack ever needs it:
        if ffprobe_exe.exists():
            os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

_setup_ffmpeg_path()

# -----------------------------
# NOW it's safe to import the rest
# -----------------------------
from PySide6.QtCore import QThread, Signal, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QProgressBar, QLineEdit, QComboBox
)

from core.transcription import transcribe_audio_path


class TranscribeWorker(QThread):
    progress = Signal(int)         # 0..100
    status = Signal(str)           # stage text
    done = Signal(str, str)        # (srt_text, output_path)
    error = Signal(str)

    def __init__(self, input_path, output_dir, model_name, whisper_lang, first_lang, second_lang):
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.model_name = model_name
        self.whisper_lang = whisper_lang
        self.first_lang = first_lang
        self.second_lang = second_lang

    def run(self):
        try:
            def progress_callback(percent: int, stage_text: str):
                self.progress.emit(int(percent))
                self.status.emit(str(stage_text))

            self.status.emit("Starting...")
            self.progress.emit(2)

            result = transcribe_audio_path(
                self.input_path,
                model_name=self.model_name,
                whisper_lang=self.whisper_lang,
                first_lang=self.first_lang,
                second_lang=self.second_lang,
                progress_cb=progress_callback
            )

            srt_text = result.get("srt", "")
            if not srt_text.strip():
                raise RuntimeError("No SRT generated (empty output).")

            self.status.emit("Saving file...")
            self.progress.emit(99)

            in_path = Path(self.input_path)
            out_dir = Path(self.output_dir) if self.output_dir else in_path.parent
            out_path = out_dir / (in_path.stem + ".srt")

            out_path.write_text(srt_text, encoding="utf-8")

            self.progress.emit(100)
            self.status.emit("Done.")
            self.done.emit(srt_text, str(out_path))

        except Exception as e:
            self.error.emit(str(e))


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Subtitle Maker (Local)")

        self.input_path = ""
        self.worker = None

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # File row
        file_row = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.btn_pick = QPushButton("Choose Video/Audio")
        self.btn_pick.clicked.connect(self.pick_file)
        file_row.addWidget(self.file_label, 1)
        file_row.addWidget(self.btn_pick)
        layout.addLayout(file_row)

        # Output row
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Save to folder (optional):"))
        self.out_dir = QLineEdit("")
        self.out_dir.setPlaceholderText("Leave blank = same folder as input")
        self.btn_out = QPushButton("Choose Folder")
        self.btn_out.clicked.connect(self.pick_folder)
        out_row.addWidget(self.out_dir, 1)
        out_row.addWidget(self.btn_out)
        layout.addLayout(out_row)

        # Model row
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Subtitle Accuracy:"))
        self.model_combo = QComboBox()
        self.model_combo.addItem("Auto (Recommended)", None)
        self.model_combo.addItem("Weak", "base")
        self.model_combo.addItem("Medium", "small")
        self.model_combo.addItem("Strong", "medium")
        model_row.addWidget(self.model_combo)
        layout.addLayout(model_row)

        # Whisper language
        whisper_row = QHBoxLayout()
        whisper_row.addWidget(QLabel("Video input language:"))
        self.whisper_combo = QComboBox()
        self.whisper_combo.addItem("Auto (detect)", None)
        self.whisper_combo.addItem("Arabic (ar)", "ar")
        self.whisper_combo.addItem("Chinese (zh)", "zh")
        self.whisper_combo.addItem("English (en)", "en")
        self.whisper_combo.addItem("Japanese (ja)", "ja")
        self.whisper_combo.addItem("Korean (ko)", "ko")
        whisper_row.addWidget(self.whisper_combo)
        layout.addLayout(whisper_row)

        # First subtitle
        sub1_row = QHBoxLayout()
        sub1_row.addWidget(QLabel("First Subtitle:"))
        self.sub1_combo = QComboBox()
        self.sub1_combo.addItem("Traditional Chinese (zh-Hant)", "zh")        
        self.sub1_combo.addItem("English (en)", "en")
        self.sub1_combo.addItem("Arabic (ar)", "ar")
        self.sub1_combo.addItem("Japanese (ja)", "ja")
        self.sub1_combo.addItem("Korean (ko)", "ko")
        sub1_row.addWidget(self.sub1_combo)
        layout.addLayout(sub1_row)

        # Second subtitle
        sub2_row = QHBoxLayout()
        sub2_row.addWidget(QLabel("Second Subtitle:"))
        self.sub2_combo = QComboBox()
        self.sub2_combo.addItem("English (en)", "en")        
        self.sub2_combo.addItem("None", None)
        self.sub2_combo.addItem("Arabic (ar)", "ar")
        self.sub2_combo.addItem("Traditional Chinese (zh-Hant)", "zh")
        self.sub2_combo.addItem("Japanese (ja)", "ja")
        self.sub2_combo.addItem("Korean (ko)", "ko")
        sub2_row.addWidget(self.sub2_combo)
        layout.addLayout(sub2_row)

        # Start button
        self.btn_start = QPushButton("Start → Generate SRT")
        self.btn_start.clicked.connect(self.start_transcribe)
        layout.addWidget(self.btn_start)

        # Elapsed
        self.elapsed_label = QLabel("Elapsed: 00:00")
        self.elapsed_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.elapsed_label)

        self._elapsed_secs = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick_elapsed)

        # Progress
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Status
        self.status = QLabel("Ready.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.setLayout(layout)

        # Your theme
        self.setStyleSheet("""
QWidget { background: #E7E5E4; color: #111827; font-size: 13px; }
QLabel { color: #111827; font-size: 15px; font-weight: 650; }
QLineEdit, QComboBox {
    background: #F8FAFC;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 8px 10px;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #2563EB; }
QComboBox { padding-right: 30px; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid #CBD5E1;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    background: #EEF2F7;
}
QComboBox::down-arrow {
    width: 0px; height: 0px;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-top: 8px solid #334155;
}
QComboBox::down-arrow:on { border-top: 8px solid #1D4ED8; }
QComboBox QAbstractItemView {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    selection-background-color: #DBEAFE;
    selection-color: #0F172A;
    outline: 0;
}
QComboBox QAbstractItemView::item { padding: 10px 12px; }
QPushButton {
    background: #2563EB;
    color: #FFFFFF;
    border: none;
    border-radius: 14px;
    padding: 10px 14px;
    font-weight: 700;
}
QPushButton:hover { background: #1D4ED8; }
QPushButton:disabled { background: #94A3B8; color: #F8FAFC; }
QProgressBar {
    background: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 12px;
    text-align: center;
    height: 18px;
    color: #0F172A;
}
QProgressBar::chunk { background: #22C55E; border-radius: 12px; }
""")

    def _tick_elapsed(self):
        self._elapsed_secs += 1
        mm = self._elapsed_secs // 60
        ss = self._elapsed_secs % 60
        self.elapsed_label.setText(f"Elapsed: {mm:02}:{ss:02}")

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose audio/video",
            "",
            "Media Files (*.mp3 *.wav *.m4a *.aac *.mp4 *.mov *.mkv *.webm);;All Files (*.*)"
        )
        if path:
            self.input_path = path
            self.file_label.setText(path)
            self.status.setText("File selected. Ready.")

    def pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.out_dir.setText(folder)

    def start_transcribe(self):
        if not self.input_path:
            QMessageBox.warning(self, "Missing file", "Please choose a file first.")
            return

        self.btn_start.setEnabled(False)
        self.btn_pick.setEnabled(False)
        self.btn_out.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText("Running...")
        self._elapsed_secs = 0
        self.elapsed_label.setText("Elapsed: 00:00")
        self._timer.start()

        self.worker = TranscribeWorker(
            self.input_path,
            self.out_dir.text().strip(),
            self.model_combo.currentData(),
            self.whisper_combo.currentData(),
            self.sub1_combo.currentData(),
            self.sub2_combo.currentData()
        )
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status.connect(self.status.setText)
        self.worker.done.connect(self.on_done)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_done(self, srt_text, output_path):
        self._timer.stop()
        self.status.setText(f"Done! Saved: {output_path}")
        QMessageBox.information(self, "Done", f"SRT saved to:\n{output_path}")
        self.btn_start.setEnabled(True)
        self.btn_pick.setEnabled(True)
        self.btn_out.setEnabled(True)

    def on_error(self, msg):
        self._timer.stop()
        self.status.setText("Error.")
        QMessageBox.critical(self, "Error", msg)
        self.btn_start.setEnabled(True)
        self.btn_pick.setEnabled(True)
        self.btn_out.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    w = App()
    w.resize(820, 400)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()