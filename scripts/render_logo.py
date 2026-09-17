from pathlib import Path

from PIL import Image
from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "assets" / "bonusdesk.svg"
PNG = ROOT / "assets" / "bonusdesk.png"
ICO = ROOT / "assets" / "bonusdesk.ico"


def main() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(SVG))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG: {SVG}")
    image = QImage(QSize(512, 512), QImage.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, 512, 512))
    painter.end()
    if not image.save(str(PNG), "PNG"):
        raise RuntimeError(f"Could not save {PNG}")
    with Image.open(PNG) as source:
        source.save(ICO, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    app.quit()


if __name__ == "__main__":
    main()
