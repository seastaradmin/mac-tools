import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from ui.pin_window import PinWindow


app = QApplication.instance() or QApplication(sys.argv)


class PinWindowTests(unittest.TestCase):

    def test_retina_pixmap_uses_logical_size(self):
        pixmap = QPixmap(1000, 500)
        pixmap.setDevicePixelRatio(2.0)

        window = PinWindow(pixmap)

        self.assertEqual(window._pixmap_logical_size(), (500, 250))
        self.assertEqual(window.width(), 500 + window.BORDER_WIDTH * 2)
        self.assertEqual(window.height(), 250 + window.BORDER_WIDTH * 2)


if __name__ == "__main__":
    unittest.main()
