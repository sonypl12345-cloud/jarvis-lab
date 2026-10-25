import ctypes, io, json, socket, threading
from ctypes import wintypes
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST="0.0.0.0"
PORT=8765
TOKEN_PATH=Path(__file__).with_name("token.txt")

def pairing_token():
    try:
        return TOKEN_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        return ""

user32=ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN=0x0002
MOUSEEVENTF_LEFTUP=0x0004
MOUSEEVENTF_RIGHTDOWN=0x0008
MOUSEEVENTF_RIGHTUP=0x0010
MOUSEEVENTF_WHEEL=0x0800
KEYEVENTF_KEYUP=0x0002
KEYEVENTF_UNICODE=0x0004
INPUT_KEYBOARD=1

VK={"BACKSPACE":0x08,"TAB":0x09,"ENTER":0x0D,"ESC":0x1B,"LEFT":0x25,"UP":0x26,"RIGHT":0x27,"DOWN":0x28}

class KEYBDINPUT(ctypes.Structure):
    _fields_=[("wVk",ctypes.c_ushort),("wScan",ctypes.c_ushort),("dwFlags",ctypes.c_ulong),("time",ctypes.c_ulong),("dwExtraInfo",ctypes.POINTER(ctypes.c_ulong))]
class INPUT_UNION(ctypes.Union):
    _fields_=[("ki",KEYBDINPUT)]
class INPUT(ctypes.Structure):
    _fields_=[("type",ctypes.c_ulong),("union",INPUT_UNION)]

def send_unicode(text):
    raw=text.encode("utf-16-le","surrogatepass")
    for i in range(0,len(raw),2):
        code=raw[i] | (raw[i+1]<<8)
        for flags in (KEYEVENTF_UNICODE,KEYEVENTF_UNICODE|KEYEVENTF_KEYUP):
            inp=INPUT(type=INPUT_KEYBOARD)
            inp.union.ki=KEYBDINPUT(0,code,flags,0,None)
            user32.SendInput(1,ctypes.byref(inp),ctypes.sizeof(inp))

def send_key(name):
    vk=VK.get((name or "").upper())
    if not vk:
        return False
    user32.keybd_event(vk,0,0,0)
    user32.keybd_event(vk,0,KEYEVENTF_KEYUP,0)
    return True

def mouse_move(dx,dy):
    p=wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    user32.SetCursorPos(p.x+int(dx),p.y+int(dy))

def mouse_click(right=False):
    if right:
        user32.mouse_event(MOUSEEVENTF_RIGHTDOWN,0,0,0,0)
        user32.mouse_event(MOUSEEVENTF_RIGHTUP,0,0,0,0)
    else:
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN,0,0,0,0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP,0,0,0,0)

def mouse_scroll(steps):
    user32.mouse_event(MOUSEEVENTF_WHEEL,0,0,int(steps)*120,0,0)

def screen_jpeg():
    from PIL import ImageGrab
    img=ImageGrab.grab(all_screens=False)
    if img.width>1440:
        h=max(1,round(img.height*1440/img.width))
        img=img.resize((1440,h))
    buf=io.BytesIO()
    img.save(buf,"JPEG",quality=67)
    return buf.getvalue()

_cam_lock=threading.Lock()
_camera=None

def camera_jpeg():
    global _camera
    import cv2
    with _cam_lock:
        if _camera is None or not _camera.isOpened():
            _camera=cv2.VideoCapture(0,cv2.CAP_DSHOW)
            _camera.set(cv2.CAP_PROP_FRAME_WIDTH,1280)
            _camera.set(cv2.CAP_PROP_FRAME_HEIGHT,720)
        ok,frame=_camera.read()
        if not ok or frame is None:
            raise RuntimeError("camera_read_failed")
        ok,enc=cv2.imencode(".jpg",frame,[int(cv2.IMWRITE_JPEG_QUALITY),72])
        if not ok:
            raise RuntimeError("camera_encode_failed")
        return enc.tobytes()

class Handler(BaseHTTPRequestHandler):
    server_version="GENESISRemote/0.2"
    def log_message(self,*args):
        return
    def _auth(self):
        tok=pairing_token()
        return bool(tok) and self.headers.get("X-Genesis-Token","")==tok
    def _json(self,obj,status=200):
        body=json.dumps(obj,separators=(",",":")).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(body)
    def _jpeg(self,body):
        self.send_response(200)
        self.send_header("Content-Type","image/jpeg")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if not self._auth():
            return self._json({"ok":False,"error":"unauthorized"},401)
        try:
            if self.path.startswith("/status"):
                return self._json({"ok":True,"host":socket.gethostname(),"screen":True,"camera":True,"control":True})
            if self.path.startswith("/screen.jpg"):
                return self._jpeg(screen_jpeg())
            if self.path.startswith("/camera.jpg"):
                return self._jpeg(camera_jpeg())
            return self._json({"ok":False,"error":"not_found"},404)
        except Exception as e:
            return self._json({"ok":False,"error":type(e).__name__},503)
    def do_POST(self):
        if not self._auth():
            return self._json({"ok":False,"error":"unauthorized"},401)
        if not self.path.startswith("/control"):
            return self._json({"ok":False,"error":"not_found"},404)
        try:
            n=min(int(self.headers.get("Content-Length","0") or "0"),16384)
            data=json.loads(self.rfile.read(n) or b"{}")
            action=str(data.get("action",""))
            a=int(data.get("a",0) or 0)
            b=int(data.get("b",0) or 0)
            text=str(data.get("text","") or "")
            if action=="mouse_move":
                mouse_move(max(-500,min(500,a)),max(-500,min(500,b)))
            elif action=="left_click":
                mouse_click(False)
            elif action=="right_click":
                mouse_click(True)
            elif action=="scroll":
                mouse_scroll(max(-12,min(12,a)))
            elif action=="type_text":
                send_unicode(text[:2048])
            elif action=="key":
                if not send_key(text):
                    return self._json({"ok":False,"error":"key_denied"},400)
            else:
                return self._json({"ok":False,"error":"action_denied"},400)
            return self._json({"ok":True})
        except Exception as e:
            return self._json({"ok":False,"error":type(e).__name__},400)

ThreadingHTTPServer((HOST,PORT),Handler).serve_forever(poll_interval=0.2)
