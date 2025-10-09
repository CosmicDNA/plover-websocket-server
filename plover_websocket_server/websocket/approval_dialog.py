"""Helper script to display a GUI approval dialog."""

import sys

from PyQt5.QtWidgets import QApplication, QMessageBox

if __name__ == "__main__":
    # Ensure a QApplication instance exists.
    app = QApplication.instance() or QApplication(sys.argv)

    remote_addr = sys.argv[1]
    reply = QMessageBox.question(
        None,
        "Plover WebSocket Server",
        f"Allow connection from {remote_addr}?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )

    # Exit with 0 for success (Yes) and 1 for failure (No).
    sys.exit(0 if reply == QMessageBox.StandardButton.Yes else 1)