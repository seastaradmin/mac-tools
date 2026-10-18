import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from ui.screenshot_overlay import ScreenshotOverlay


app = QApplication.instance() or QApplication(sys.argv)


class ScreenshotOverlayTests(unittest.TestCase):

    def test_logical_selection_maps_to_retina_image_pixels(self):
        overlay = ScreenshotOverlay()
        overlay.resize(100, 50)
        overlay._screen_pixmap = QPixmap(200, 100)
        overlay._selection = QRect(10, 5, 20, 10)

        overlay._sync_image_scale()

        self.assertEqual(overlay._selection_to_image_rect(), QRect(20, 10, 40, 20))

    def test_mouse_position_maps_to_selected_image_pixels(self):
        overlay = ScreenshotOverlay()
        overlay.resize(100, 50)
        overlay._screen_pixmap = QPixmap(200, 100)
        overlay._selection = QRect(10, 5, 20, 10)
        overlay._edit_pixmap = QPixmap(40, 20)

        overlay._sync_image_scale()

        self.assertEqual(overlay._to_image_pos(QPoint(15, 8)), QPoint(10, 6))

    def test_pin_emits_selected_pixmap(self):
        overlay = ScreenshotOverlay()
        overlay.resize(100, 50)
        overlay._screen_pixmap = QPixmap(200, 100)
        overlay._edit_pixmap = QPixmap(40, 20)
        overlay._sync_image_scale()
        received = []
        overlay.pin_requested.connect(received.append)

        overlay.pin()

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].size(), overlay._edit_pixmap.size())
        self.assertEqual(received[0].devicePixelRatio(), 2.0)
        self.assertEqual(received[0].deviceIndependentSize().width(), 20)


if __name__ == "__main__":
    unittest.main()
