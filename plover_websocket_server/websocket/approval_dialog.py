"""Helper script to display a GUI approval dialog."""

import sys
from pathlib import Path

from plover.oslayer.config import ASSETS_DIR
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

if __name__ == "__main__":
    # Ensure a QApplication instance exists.
    app = QApplication(sys.argv)

    # Set the Plover icon for the window and message box
    # plover_icon_path = Path(ASSETS_DIR) / "plover-icon.svg"
    plover_icon_path = Path(ASSETS_DIR) / "plover.png"
    plover_icon = QIcon(str(plover_icon_path))
    app.setWindowIcon(plover_icon)

    remote_addr = sys.argv[1]
    msg_box = QMessageBox()
    msg_box.setWindowTitle("Plover WebSocket Server")
    msg_box.setText("A new client is trying to connect.")
    msg_box.setInformativeText("Do you want to allow this connection?")
    msg_box.setDetailedText(f"Connection details:\n{remote_addr}")
    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

    # Set the window to stay on top to ensure it gets focus.
    msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

    # Bring the window to the front and give it focus.
    msg_box.raise_()
    msg_box.activateWindow()

    reply = msg_box.exec()

    # Exit with 0 for success (Yes) and 1 for failure (No).
    sys.exit(0 if reply == QMessageBox.StandardButton.Yes else 1)
