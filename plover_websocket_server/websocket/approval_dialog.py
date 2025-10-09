"""Helper script to display a GUI approval dialog."""

import sys

from PyQt5.QtWidgets import QApplication, QMessageBox

if __name__ == "__main__":
    # Ensure a QApplication instance exists.
    app = QApplication(sys.argv)

    remote_addr = sys.argv[1]
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setWindowTitle("Plover WebSocket Server")
    msg_box.setText("A new client is trying to connect.")
    msg_box.setInformativeText("Do you want to allow this connection?")
    msg_box.setDetailedText(f"Connection details:\n{remote_addr}")
    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    reply = msg_box.exec()

    # Exit with 0 for success (Yes) and 1 for failure (No).
    sys.exit(0 if reply == QMessageBox.StandardButton.Yes else 1)