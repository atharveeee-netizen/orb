import sys
import threading
import time
import socket
import pyautogui
from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QPainter, QPen, QColor
import qrcode
import os
import io
import base64

# Disable PyAutoGUI failsafe to avoid crashing when mouse hits corners
pyautogui.FAILSAFE = False
# Minimal delay for smoother trackpad
pyautogui.PAUSE = 0.0

app = Flask(__name__, static_folder='static')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class Communicate(QObject):
    add_stroke = pyqtSignal(list)
    clear_canvas = pyqtSignal()

class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        # Transparent, always on top, click-through
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool | 
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.showFullScreen()
        self.strokes = []
        
        self.c = Communicate()
        self.c.add_stroke.connect(self.on_add_stroke)
        self.c.clear_canvas.connect(self.on_clear_canvas)

    def on_add_stroke(self, stroke):
        self.strokes.append(stroke)
        self.update()
        
    def on_clear_canvas(self):
        self.strokes = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(255, 50, 50), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        
        screen_width = self.width()
        screen_height = self.height()
        
        for stroke in self.strokes:
            for i in range(len(stroke)-1):
                # Points from web client are normalized 0.0-1.0
                x1 = int(stroke[i][0] * screen_width)
                y1 = int(stroke[i][1] * screen_height)
                x2 = int(stroke[i+1][0] * screen_width)
                y2 = int(stroke[i+1][1] * screen_height)
                painter.drawLine(x1, y1, x2, y2)

overlay = None

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/qr')
def qr():
    ip = get_local_ip()
    url = f"http://{ip}:8745"
    try:
        img = qrcode.make(url)
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        img_b64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
        return f'<img src="data:image/png;base64,{img_b64}" width="200" height="200">'
    except Exception as e:
        return f"QR Code requires 'qrcode' and 'Pillow' packages: {e}"

@socketio.on('mouse_move')
def handle_mouse_move(data):
    dx = data.get('dx', 0)
    dy = data.get('dy', 0)
    if dx != 0 or dy != 0:
        pyautogui.move(dx * 1.5, dy * 1.5, _pause=False)

@socketio.on('mouse_click')
def handle_mouse_click(data):
    btn = data.get('button', 'left')
    pyautogui.click(button=btn)

@socketio.on('mouse_scroll')
def handle_mouse_scroll(data):
    dy = data.get('dy', 0)
    pyautogui.scroll(-int(dy * 10))

@socketio.on('stroke')
def handle_stroke(data):
    if overlay:
        overlay.c.add_stroke.emit(data['points'])

@socketio.on('clear')
def handle_clear():
    if overlay:
        overlay.c.clear_canvas.emit()

@socketio.on('slide')
def handle_slide(data):
    action = data.get('action')
    if action == 'next':
        pyautogui.press('right')
    elif action == 'prev':
        pyautogui.press('left')
    elif action == 'play':
        pyautogui.press('f5')

def run_flask():
    socketio.run(app, host='0.0.0.0', port=8745, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    # Start Flask server in a separate thread
    threading.Thread(target=run_flask, daemon=True).start()
    
    ip = get_local_ip()
    print("=========================================")
    print(" Orb PC Server is running!")
    print(f" Connect your phone/iPad to: http://{ip}:8745")
    print("=========================================")
    
    # Run PyQt5 application in the main thread
    qt_app = QApplication(sys.argv)
    overlay = OverlayWindow()
    sys.exit(qt_app.exec_())
