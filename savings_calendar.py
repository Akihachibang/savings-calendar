# -*- coding: utf-8 -*-
"""
Savings Calendar v2 - ปฏิทินเก็บเงิน
รัน: python savings_calendar_v2.py
ถ้าจะใช้รูปพื้นหลัง ติดตั้งครั้งเดียว: pip install pillow
ข้อมูลเก็บที่ %APPDATA%\\Savings Calendar\\
"""
import ctypes, itertools, json, math, os, random, re, shutil, subprocess, sys, time, uuid
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, font as tkfont

# ---- ทำให้คมชัดบน Windows (ปิดการขยายแบบเบลอของระบบ) ----
if sys.platform.startswith("win"):
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ---- ติดตั้ง Pillow ให้อัตโนมัติเมื่อเปิดโปรแกรมครั้งแรก (กรณีรันจาก .py) ----
def _ensure_pillow():
    try:
        import PIL  # noqa: F401
        return
    except ImportError:
        pass
    if getattr(sys, "frozen", False) or os.environ.get("SC_RESTARTED"):
        return  # แบบ .exe มี Pillow รวมมาแล้ว / ป้องกันวนซ้ำ
    try:
        w = tk.Tk()
        w.title("Savings Calendar")
        w.geometry("420x110+300+250")
        tk.Label(w, text="กำลังติดตั้งส่วนเสริมสำหรับรูปพื้นหลัง (ครั้งเดียว)\nกรุณารอสักครู่ ต้องต่ออินเทอร์เน็ต...",
                 font=("Tahoma", 11), pady=24).pack()
        w.update()
        flags = 0x08000000 if sys.platform.startswith("win") else 0
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--quiet", "pillow"], creationflags=flags)
        w.destroy()
        subprocess.Popen([sys.executable] + sys.argv, env={**os.environ, "SC_RESTARTED": "1"})
        sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        try:
            w.destroy()
        except Exception:
            pass


_ensure_pillow()
try:
    from PIL import Image, ImageFilter, ImageTk
    RES = getattr(Image, "Resampling", Image).BILINEAR
except Exception:
    Image = None


APP = "Savings Calendar"
BASE = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
ROOT_DIR = os.path.join(BASE, APP)
CFG_FILE = os.path.join(ROOT_DIR, "config.json")
DATA_FILE = os.path.join(ROOT_DIR, "tables.json")
MAX_DAYS = 1500
WIN_W, WIN_H = 1280, 720  # ขนาดหน้าต่าง HD (เปลี่ยนเป็น 1920, 1080 ได้ถ้าอยากได้ Full HD)
FONT = "Tahoma"
SC = 1.0  # ตัวคูณความละเอียดหน้าจอ


def S(v):
    return int(round(v * SC))


THEMES = {
    "midnight": dict(name="เที่ยงคืน", bg="#0f1117", card="#1a1d27", cell="#242838", line="#2d3245", fg="#f3f4f8", sub="#8b90a3"),
    "snow": dict(name="หิมะ", bg="#f1f3f8", card="#ffffff", cell="#e9edf5", line="#dde1ea", fg="#1b1e2b", sub="#6b7080"),
    "ocean": dict(name="มหาสมุทร", bg="#0a1c2c", card="#11304a", cell="#194266", line="#21507a", fg="#eaf6ff", sub="#8fb3cc"),
    "sakura": dict(name="ซากุระ", bg="#fff0f4", card="#ffffff", cell="#fde2ea", line="#f5cfda", fg="#3a1f2b", sub="#9a6b7c"),
    "forest": dict(name="ป่าเขียว", bg="#0d1a13", card="#15281e", cell="#1e3829", line="#2a4a37", fg="#e9f7ee", sub="#8fb5a0"),
}
THEME_FX = {"midnight": "stars", "snow": "snow", "ocean": "bubbles", "sakura": "petals", "forest": "fireflies"}
FX_NAME = {"midnight": "ดาวระยิบระยับ", "snow": "หิมะตก", "ocean": "ฟองอากาศ", "sakura": "กลีบซากุระร่วง", "forest": "หิ่งห้อย"}
PETALS = ["#ffb7c9", "#ff9db6", "#ffd3de", "#ffc2d1"]
ACCENTS = ["#6c5ce7", "#00b894", "#ff7675", "#fdcb6e", "#0984e3", "#e17055", "#e84393"]
DEFAULT_CFG = dict(theme="midnight", accent="#6c5ce7", bg=None, bg_image=None, dim=0.35, blur=False,
                   shape="pill", anim=True, fx=2)


# ---------- helpers ----------
def load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(path, obj):
    os.makedirs(ROOT_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, k):
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * k) for x, y in zip(rgb(a), rgb(b)))


def fmt(n):
    return f"{n:,.0f}" if float(n).is_integer() else f"{n:,.2f}"


def num(x):
    return int(x) if float(x).is_integer() else round(float(x), 2)


def ease(k):
    return 1 - (1 - k) ** 3


def rrect(c, x1, y1, x2, y2, r, **kw):
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    if r < 1:
        return c.create_rectangle(x1, y1, x2, y2, **kw)
    p = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
         x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(p, smooth=True, splinesteps=28, **kw)


# ---------- ตรรกะเครื่องคิดเลข ----------
OPS = "+−×÷"
NUM = r"(?:\d+\.?\d*|\.\d+)"


def fmtnum(v):
    if v != v or abs(v) == float("inf"):
        raise ZeroDivisionError
    if abs(v) < 1e-12:
        return "0"
    if v == int(v) and abs(v) < 1e15:
        return str(int(v)).replace("-", "−")
    t = f"{v:.10g}"
    if "e" in t:
        if abs(v) < 1:
            t = f"{v:.12f}".rstrip("0").rstrip(".")
        else:
            raise OverflowError
    return t.replace("-", "−")


def calc_eval(expr):
    """คำนวณนิพจน์ (ปิดวงเล็บที่ค้างให้อัตโนมัติ) -> float"""
    e = expr.rstrip(OPS)
    e += ")" * (e.count("(") - e.count(")"))
    e = e.replace("×", "*").replace("÷", "/").replace("−", "-").replace("%", "/100")
    e = re.sub(r"(?<![\d.])0+(?=\d)", "", e)
    if not e or not re.fullmatch(r"[0-9+\-*/.()]+", e):
        raise ValueError
    return float(eval(e, {"__builtins__": {}}, {}))


def last_operand(expr):
    """(ตำแหน่งเริ่ม, ข้อความ) ของตัวเลข/กลุ่มวงเล็บท้ายสุด รวมเครื่องหมายลบนำหน้า"""
    st = None
    if expr.endswith(")"):
        d = 0
        for i in range(len(expr) - 1, -1, -1):
            d += (expr[i] == ")") - (expr[i] == "(")
            if d == 0:
                st = i
                break
    else:
        m = re.search(NUM + "$", expr)
        st = m.start() if m else None
    if st is None:
        return None
    if st > 0 and expr[st - 1] == "−" and (st == 1 or expr[st - 2] in OPS + "("):
        st -= 1
    return st, expr[st:]


def put(expr, st, out):
    """แทนที่ expr[st:] ด้วย out (ครอบวงเล็บถ้าเป็นค่าติดลบกลางนิพจน์)"""
    if out.startswith("−") and st > 0 and expr[st - 1] != "(":
        out = f"({out})"
    return expr[:st] + out


def implicit_mul(c):
    if c["expr"] and (c["expr"][-1].isdigit() or c["expr"][-1] in ").%"):
        c["expr"] += "×"


def cur_value(c):
    try:
        return calc_eval(c["expr"])
    except Exception:
        op = last_operand(c["expr"])
        try:
            return calc_eval(op[1]) if op else 0.0
        except Exception:
            return 0.0


def calc_press(c, k):
    c.setdefault("mem", 0.0)
    if k != "=" and c.get("msg"):
        c["msg"] = ""
    ex = c["expr"]
    if k == "AC":
        c.update(expr="", top="", just=False)
    elif k == "⌫":
        c.update(expr="" if c["just"] else ex[:-1], top="" if c["just"] else c["top"], just=False)
    elif k == "=":
        if not ex:
            return
        try:
            r = calc_eval(ex)
            c.update(top=ex + ")" * (ex.count("(") - ex.count(")")) + " =", expr=fmtnum(r), just=True)
        except ZeroDivisionError:
            c.update(expr="", top="", just=False, msg="หารด้วยศูนย์ไม่ได้")
        except OverflowError:
            c.update(expr="", top="", just=False, msg="ตัวเลขใหญ่เกินไป")
        except Exception:
            c.update(expr="", top="", just=False, msg="คำนวณไม่ได้")
    elif k in ("x²", "√", "1/x", "±"):
        op = (0, ex) if c["just"] else last_operand(ex)
        if not op:
            return
        st, txt = op
        try:
            v = calc_eval(txt)
            if k == "√" and v < 0:
                raise ValueError
            r = {"x²": lambda: v * v, "√": lambda: math.sqrt(v), "1/x": lambda: 1 / v, "±": lambda: -v}[k]()
            out = fmtnum(r)
        except ZeroDivisionError:
            c.update(expr="", top="", just=False, msg="หารด้วยศูนย์ไม่ได้")
            return
        except Exception:
            c.update(expr="", top="", just=False, msg="ค่าไม่ถูกต้อง")
            return
        if c["just"]:
            c.update(top=f"{k}({txt})", expr=out)
        else:
            c["expr"] = put(ex, st, out)
    elif k in ("MC", "MR", "M+", "M−"):
        if k == "MC":
            c["mem"] = 0.0
        elif k == "MR":
            if c["just"]:
                c.update(expr="", top="", just=False)
            ex = c["expr"]
            m = re.search(NUM + "$", ex)
            out = fmtnum(c["mem"])
            if m:
                c["expr"] = put(ex, m.start(), out)
            else:
                implicit_mul(c)
                c["expr"] = put(c["expr"], len(c["expr"]), out)
        else:
            if c["expr"]:
                try:
                    v = cur_value(c)
                    c["mem"] += v * (1 if k == "M+" else -1)
                    c.update(expr=fmtnum(v), top="", just=True)
                except Exception:
                    pass
    elif k in "0123456789.":
        if c["just"]:
            c.update(expr="", top="", just=False)
        if c["expr"] and c["expr"][-1] in ")%":
            c["expr"] += "×"
        seg = re.split(r"[+−×÷%()]", c["expr"])[-1]
        if k == "." and "." in seg:
            return
        if k == "." and seg == "":
            k = "0."
        if seg == "0" and k != ".":
            c["expr"] = c["expr"][:-1]
        c["expr"] += k
    elif k in OPS:
        if c["just"]:
            c.update(just=False, top="")
        ex = c["expr"]
        if not ex or ex[-1] == "(":
            if k == "−":
                c["expr"] += "−"
            elif ex == "":
                c["expr"] = "0" + k
        elif ex[-1] in OPS:
            if k == "−" and ex[-1] in "×÷":
                c["expr"] += "−"
            else:
                c["expr"] = ex[:-1] + k
                if c["expr"][-1:] in OPS and len(c["expr"]) > 1 and c["expr"][-2] in "×÷" and k != "−":
                    c["expr"] = c["expr"][:-2] + k
        else:
            c["expr"] += k
    elif k == "(":
        if c["just"]:
            c.update(expr="", top="", just=False)
        implicit_mul(c)
        c["expr"] += "("
    elif k == ")":
        ex = c["expr"]
        if ex.count("(") > ex.count(")") and ex[-1] not in OPS + "(":
            c["expr"] += ")"
    elif k == "%":
        if c["just"]:
            c.update(just=False, top="")
        if c["expr"] and (c["expr"][-1].isdigit() or c["expr"][-1] == ")"):
            c["expr"] += "%"


def pretty(t):
    m = re.fullmatch(r"(−?)(\d+)(\.\d*)?(%?)", t)
    if not m:
        return t
    sg, i, d, pc = m.groups()
    return f"{sg}{int(i):,}{d or ''}{pc}"


def calc_display(c):
    """(บรรทัดนิพจน์, ตัวเลขหลักบนจอ)"""
    ex = c["expr"]
    if c.get("msg"):
        return "", c["msg"]
    if c["just"] or not ex:
        return c["top"], pretty(ex or "0")
    top = re.sub(r"(?<=[\d.)%])([+−×÷])", r" \1 ", ex)
    top = "…" + top[-30:] if len(top) > 31 else top
    if ex[-1].isdigit() or ex[-1] == ".":
        op = last_operand(ex)
        main = pretty(op[1]) if op and not op[1].startswith("(") else pretty(re.findall(NUM, ex)[-1])
    else:
        try:
            main = pretty(fmtnum(calc_eval(ex)))
        except Exception:
            main = "0"
    return top, main


# ---------- หน้า (แคนวาสเดียววาดทุกอย่าง เพื่อให้วางรูปพื้นหลังได้) ----------
class Page(tk.Canvas):
    def __init__(p, app, master, build):
        super().__init__(master, highlightthickness=0, bd=0, bg=app.t["bg"], yscrollincrement=S(26))
        p.app, p.build = app, build
        p.W = p.H = 0
        p.job = None
        p.ids = itertools.count()
        p.vars, p.ents, p.st = {}, {}, {}
        p.bgph = None
        p.on_change = lambda: None
        p._drag = False
        p.parts, p.fx_job, p.fx_kind, p.fx_t = [], None, None, 0
        p.closebtn, p.nobg, p.nofx, p.win = True, False, False, None
        p.bind("<Configure>", p._cfg)
        p.bind("<ButtonPress-1>", p._dstart, add="+")
        p.bind("<B1-Motion>", p._dmove, add="+")

    def _cfg(p, e):
        if (e.width, e.height) == (p.W, p.H):
            return
        first = p.W == 0
        p.W, p.H = e.width, e.height
        if first:
            p.render()
        else:
            if p.job:
                p.after_cancel(p.job)
            p.job = p.after(50, p.render)

    def render(p):
        p.job = None
        if not p.winfo_exists():
            return
        keep = p.yview()[0]
        p.fx_stop()
        p.delete("all")
        ph = None if p.nobg else p.app.bg_photo(p.W, p.H)
        p.bgph = ph
        if ph:
            p.create_image(0, 0, image=ph, anchor="nw", tags="bg")
        ch = p.build(p, p.W / SC, p.H / SC) or 0
        p.fx_start()
        p.configure(scrollregion=(0, 0, p.W, max(S(ch), p.H)))
        p.yview_moveto(keep)
        p.fix_bg()

    def fix_bg(p):
        p.tag_lower("fx")
        if p.bgph:
            p.tag_lower("bg")
            p.coords("bg", 0, p.canvasy(0))
        p.draw_close()

    def draw_close(p):
        """ปุ่มปิดโปรแกรมมุมขวาล่าง (อยู่กับที่แม้เลื่อนหน้า)"""
        p.delete("close")
        if not p.closebtn:
            return
        top = p.canvasy(0) / SC
        p.button(p.W / SC - 154, top + p.H / SC - 66, 130, 44, "✕  ปิดโปรแกรม", p.app.root.destroy,
                 "danger", size=14, group="close")

    def _dstart(p, e):
        tags = [x for x in p.gettags("current") if x != "current"]
        p._drag = not (set(tags) - {"bg", "fx"})
        if p._drag:
            w = p.win or p.app.root
            p._dx, p._dy = e.x_root - w.winfo_x(), e.y_root - w.winfo_y()

    def _dmove(p, e):
        if p._drag:
            (p.win or p.app.root).geometry(f"+{e.x_root - p._dx}+{e.y_root - p._dy}")

    # --- เอฟเฟกต์พื้นหลังตามธีม ---
    def fx_stop(p):
        if p.fx_job:
            try:
                p.after_cancel(p.fx_job)
            except Exception:
                pass
            p.fx_job = None
        p.parts = []

    def fx_start(p):
        p.fx_stop()
        a = p.app
        kind, lv = THEME_FX.get(a.cfg["theme"]), a.cfg.get("fx", 2)
        if p.nofx or not kind or not lv or p.W < 50:
            return
        bg = a.t["bg"]
        W, H, rnd = p.W, p.H, random.random
        n = max(8, int({1: 16, 2: 34, 3: 64}[lv] * min(2.0, max(.4, W * H / (SC * SC * 1280 * 720)))))
        p.fx_kind = kind
        for _ in range(n):
            q = dict(x=rnd() * W, y=rnd() * H, ph=rnd() * 6.28, ps=.8 + rnd() * 1.6, vx=0, vy=0)
            if kind == "snow":
                q.update(r=(1.5 + rnd() * 3.5) * SC, vy=(25 + rnd() * 45) * SC, vx=(rnd() - .5) * 10 * SC)
                st = dict(fill="#ffffff", outline=mix(bg, "#7d96c8", .8))
            elif kind == "petals":
                q.update(r=(4 + rnd() * 4) * SC, vy=(35 + rnd() * 40) * SC, vx=(15 + rnd() * 25) * SC)
                st = dict(fill=random.choice(PETALS), outline="")
            elif kind == "bubbles":
                q.update(r=(3 + rnd() * 12) * SC, vy=-(25 + rnd() * 45) * SC)
                st = dict(fill="", outline=mix(bg, "#9fdcff", .6), width=S(1.5))
            elif kind == "fireflies":
                q.update(r=(2 + rnd() * 2) * SC, vx=(rnd() - .5) * 20 * SC, vy=(rnd() - .5) * 20 * SC)
                st = dict(fill=bg, outline="")
            else:
                q.update(r=(.8 + rnd() * 1.6) * SC, ps=1 + rnd() * 2.5)
                st = dict(fill=bg, outline="")
            q["id"] = p.create_oval(0, 0, 0, 0, tags="fx", **st)
            p.parts.append(q)
        p.fx_t = time.time()
        p.fx_tick()

    def fx_tick(p):
        p.fx_job = None
        try:
            if not p.winfo_exists() or not p.parts:
                return
        except tk.TclError:
            return
        now = time.time()
        dt, p.fx_t = min(.08, now - p.fx_t), now
        k, top, W, H, bg = p.fx_kind, p.canvasy(0), p.W, p.H, p.app.t["bg"]
        for q in p.parts:
            q["ph"] += q["ps"] * dt
            sn, r = math.sin(q["ph"]), q["r"]
            rx = ry = r
            if k == "snow":
                q["x"] += (q["vx"] + sn * 18 * SC) * dt
                q["y"] += q["vy"] * dt
            elif k == "petals":
                q["x"] += (q["vx"] + sn * 30 * SC) * dt
                q["y"] += (q["vy"] + abs(sn) * 15 * SC) * dt
                rx, ry = r * 1.5, r * (.4 + .5 * abs(math.cos(q["ph"] * 1.7)))
            elif k == "bubbles":
                q["x"] += sn * 14 * SC * dt
                q["y"] += q["vy"] * dt
            elif k == "fireflies":
                q["x"] += (q["vx"] + sn * 16 * SC) * dt
                q["y"] += (q["vy"] + math.cos(q["ph"] * .8) * 16 * SC) * dt
                p.itemconfig(q["id"], fill=mix(bg, "#e6ff7a", .12 + .88 * sn * sn))
            else:
                p.itemconfig(q["id"], fill=mix(bg, "#ffffff", .12 + .88 * abs(sn)))
            m = r * 2 + 20 * SC
            if q["y"] > H + m:
                q["y"], q["x"] = -m, random.random() * W
            elif q["y"] < -m:
                q["y"], q["x"] = H + m, random.random() * W
            if q["x"] > W + m:
                q["x"] = -m
            elif q["x"] < -m:
                q["x"] = W + m
            p.coords(q["id"], q["x"] - rx, top + q["y"] - ry, q["x"] + rx, top + q["y"] + ry)
        p.fx_job = p.after(33, p.fx_tick)

    def scroll(p, n):
        p.yview_scroll(n, "units")
        p.fix_bg()

    # --- วาดด้วยหน่วย dp (คูณความละเอียดให้เอง) ---
    def rr(p, x1, y1, x2, y2, r, **kw):
        kw.setdefault("outline", "")
        if "width" in kw:
            kw["width"] = S(kw["width"])
        return rrect(p, S(x1), S(y1), S(x2), S(y2), S(r), **kw)

    def tx(p, x, y, text, size=16, bold=False, **kw):
        kw.setdefault("fill", p.app.t["fg"])
        return p.create_text(S(x), S(y), text=text, font=(FONT, -S(size), "bold" if bold else "normal"), **kw)

    def click(p, tg, cmd):
        p.tag_bind(tg, "<Button-1>", lambda e: cmd())
        p.tag_bind(tg, "<Enter>", lambda e: p.configure(cursor="hand2"))
        p.tag_bind(tg, "<Leave>", lambda e: p.configure(cursor=""))

    def button(p, x, y, w, h, text, cmd, kind="primary", size=16, base=None, group=None):
        a = p.app
        t, ac = a.t, a.accent
        if kind == "primary":
            b, hv, fg = ac, mix(ac, "#ffffff", .2), "#ffffff"
        elif kind == "danger":
            b, hv, fg = "#e5484d", "#ff6369", "#ffffff"
        else:
            b = base or t["card"]
            hv, fg = mix(b, ac, .3), t["fg"]
        tg = f"b{next(p.ids)}"
        tags = (tg, group) if group else tg
        r = p.rr(x, y, x + w, y + h, h / 2, fill=b, tags=tags)
        p.tx(x + w / 2, y + h / 2, text, size, True, fill=fg, tags=tags)

        def to(c):
            a.tween(130, lambda k, c0=p.itemcget(r, "fill"): p.itemconfig(r, fill=mix(c0, c, k)), key=(p, r))

        def up(e):
            if tg in p.gettags("current"):
                to(hv)
                cmd()
        p.tag_bind(tg, "<Enter>", lambda e: (p.configure(cursor="hand2"), to(hv)))
        p.tag_bind(tg, "<Leave>", lambda e: (p.configure(cursor=""), to(b)))
        p.tag_bind(tg, "<ButtonPress-1>", lambda e: (a.tw.pop((p, r), None), p.itemconfig(r, fill=mix(b, "#000000", .18))))
        p.tag_bind(tg, "<ButtonRelease-1>", up)

    def entry(p, key, x, y, w, h):
        a = p.app
        t = a.t
        tg = "pill_" + key
        p.rr(x, y, x + w, y + h, h / 2, fill=t["cell"], outline=t["line"], width=2, tags=tg)
        e = p.ents.get(key)
        if e is None:
            v = p.vars[key] = tk.StringVar()
            e = p.ents[key] = tk.Entry(p, textvariable=v, bd=0, relief="flat", justify="center", highlightthickness=0,
                                       font=(FONT, -S(19)), bg=t["cell"], fg=t["fg"], insertbackground=t["fg"])
            v.trace_add("write", lambda *_: p.on_change())
            e.bind("<FocusIn>", lambda ev: p.itemconfig(tg, outline=a.accent))
            e.bind("<FocusOut>", lambda ev: p.itemconfig(tg, outline=t["line"]))
        p.tag_bind(tg, "<Button-1>", lambda ev: e.focus_set())
        p.create_window(S(x + w / 2), S(y + h / 2), window=e, width=S(w - 44), height=S(h - 22))
        return e


# ---------- โปรแกรมหลัก ----------
class App:
    def __init__(s):
        global FONT, SC
        s.root = tk.Tk()
        SC = max(1.0, s.root.winfo_fpixels("1i") / 96)
        s.root.title("ปฏิทินเก็บเงิน • Savings Calendar")
        sw, sh = s.root.winfo_screenwidth(), s.root.winfo_screenheight()
        ww, wh = min(S(WIN_W), sw - 40), min(S(WIN_H), sh - 60)
        s.root.geometry(f"{ww}x{wh}+{(sw - ww) // 2}+{(sh - wh) // 2}")
        s.root.overrideredirect(True)  # ไม่มีแถบ title bar
        fams = set(tkfont.families())
        FONT = next((f for f in ("Leelawadee UI", "Tahoma", "Segoe UI") if f in fams), "TkDefaultFont")
        os.makedirs(ROOT_DIR, exist_ok=True)  # สร้าง %appdata%\Savings Calendar
        s.cfg = {**DEFAULT_CFG, **load(CFG_FILE, {})}
        s.tables = load(DATA_FILE, [])
        save(CFG_FILE, s.cfg)
        s.stage = tk.Frame(s.root, bd=0)
        s.stage.pack(fill="both", expand=True)
        s.cur = None
        s.busy = False
        s.tw = {}
        s.calc = dict(expr="", top="", msg="", just=False, mem=0.0)
        s.calc_win = s.calc_upd = None
        s._src = s._src_key = s._ph = s._ph_key = None
        s.apply_theme()
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            s.root.bind_all(ev, s.wheel)
        s.show(s.home, 0)
        s.root.after(80, s._taskbar)
        s.root.after(120, s.root.focus_force)

    def _taskbar(s):
        """ให้หน้าต่างไร้ขอบยังโผล่บน taskbar (Windows)"""
        if not sys.platform.startswith("win"):
            return
        try:
            u = ctypes.windll.user32
            hwnd = u.GetParent(s.root.winfo_id())
            st = u.GetWindowLongW(hwnd, -20)
            u.SetWindowLongW(hwnd, -20, (st & ~0x80) | 0x40000)
            s.root.withdraw()
            s.root.after(10, s.root.deiconify)
        except Exception:
            pass

    # ---- ธีม / พื้นหลัง ----
    def apply_theme(s):
        t = dict(THEMES.get(s.cfg["theme"], THEMES["midnight"]))
        bg = s.cfg.get("bg")
        if bg:
            dark = sum(rgb(bg)) < 380
            if dark:
                t.update(bg=bg, card=mix(bg, "#ffffff", .07), cell=mix(bg, "#ffffff", .13), line=mix(bg, "#ffffff", .18),
                         fg="#f3f4f8", sub="#9a9fb2")
            else:
                t.update(bg=bg, card=mix(bg, "#ffffff", .65), cell=mix(bg, "#000000", .06), line=mix(bg, "#000000", .12),
                         fg="#1b1e2b", sub="#6b7080")
        s.t, s.accent = t, s.cfg["accent"]
        s.root.configure(bg=t["bg"])
        s.stage.configure(bg=t["bg"])

    def bg_photo(s, W, H):
        name = s.cfg.get("bg_image")
        if not (name and Image and W > 10 and H > 10):
            return None
        path = os.path.join(ROOT_DIR, name)
        key = (path, s.cfg["blur"], s.cfg["dim"], s.t["bg"])
        if s._src_key != key:
            s._src_key, s._ph_key = key, None
            try:
                im = Image.open(path).convert("RGB")
                im.thumbnail((1920, 1920))
                if s.cfg["blur"]:
                    im = im.filter(ImageFilter.GaussianBlur(max(im.size) / 160))
                if s.cfg["dim"] > 0:
                    im = Image.blend(im, Image.new("RGB", im.size, s.t["bg"]), s.cfg["dim"])
                s._src = im
            except Exception:
                s._src = None
        if not s._src:
            return None
        k2 = (W, H, key)
        if s._ph_key != k2:
            iw, ih = s._src.size
            k = max(W / iw, H / ih)
            nw, nh = max(W, int(iw * k + .5)), max(H, int(ih * k + .5))
            im = s._src.resize((nw, nh), RES)
            l, tp = (nw - W) // 2, (nh - H) // 2
            s._ph = ImageTk.PhotoImage(im.crop((l, tp, l + W, tp + H)))
            s._ph_key = k2
        return s._ph

    def set_cfg(s, **kw):
        s.cfg.update(kw)
        save(CFG_FILE, s.cfg)
        s.apply_theme()
        s.show(s.settings, 0)

    def persist(s):
        save(DATA_FILE, s.tables)

    def wheel(s, e):
        try:
            if s.cur and s.cur.winfo_exists():
                s.cur.scroll(-3 if (e.delta > 0 or getattr(e, "num", 0) == 4) else 3)
        except tk.TclError:
            pass

    def tween(s, ms, fn, done=None, key=None):
        tok = object()
        if key is not None:
            s.tw[key] = tok
        if not s.cfg["anim"]:
            try:
                fn(1.0)
            except tk.TclError:
                pass
            if done:
                done()
            return
        t0 = time.time()

        def step():
            if key is not None and s.tw.get(key) is not tok:
                return
            k = min(1.0, (time.time() - t0) * 1000 / ms)
            try:
                fn(ease(k))
            except tk.TclError:
                return
            if k < 1:
                s.root.after(12, step)
            elif done:
                done()
        step()

    # ---- เปลี่ยนหน้าแบบสไลด์ ----
    def show(s, builder, d=1):
        if s.busy:
            return
        new = Page(s, s.stage, builder)
        old, s.cur = s.cur, new
        if old is None or d == 0 or not s.cfg["anim"]:
            new.place(x=0, y=0, relwidth=1, relheight=1)
            if old:
                old.destroy()
            return
        s.busy = True
        new.place(relx=d, y=0, relwidth=1, relheight=1)

        def f(k):
            new.place_configure(relx=d * (1 - k))
            old.place_configure(relx=-d * k * .3)

        def done():
            old.destroy()
            new.place_configure(relx=0)
            s.busy = False
        s.tween(340, f, done)

    def header(s, p, w, title, back=None, left=None, gear=False, size=34):
        if back:
            p.button(28, 20, 46, 46, "←", back, "ghost", size=22)
        if left:
            p.tx(30, 44, left, 22, True, anchor="w", fill=s.accent)
        p.tx(w / 2, 44, title, size, True)
        if gear:
            p.button(w - 74, 20, 46, 46, "⚙", lambda: s.show(s.settings, 1), "ghost", size=22)
        return 88

    # ---- หน้าหลัก ----
    def home(s, p, w, h):
        t = s.t
        y = s.header(p, w, "หน้าหลัก", left="ปฏิทินเก็บเงิน", gear=True)
        p.button(32, y, 280, 56, "＋  สร้างตารางเก็บเงิน", lambda: s.show(s.create, 1), size=17)
        p.button(w - 32 - 220, y, 220, 56, "🧮  เครื่องคิดเลข", s.toggle_calc, "ghost", size=17)
        y += 56 + 22
        p.create_line(S(32), S(y), S(w - 32), S(y), fill=t["line"], width=S(2))
        p.tx(32, y + 32, "ตารางที่สร้างไว้", 22, True, anchor="w")
        y += 64
        if not s.tables:
            p.tx(w / 2, y + 90, "🐷", 60)
            p.tx(w / 2, y + 170, "ยังไม่มีตารางเก็บเงิน", 22, True)
            p.tx(w / 2, y + 206, "กดปุ่ม “สร้างตารางเก็บเงิน” เพื่อเริ่มออมวันนี้", 16, fill=t["sub"])
            return 0
        cw, ch, gap = 350, 146, 20
        cols = max(1, int((w - 64 + gap) // (cw + gap)))
        for i, tb in enumerate(s.tables):
            x, yy = 32 + (i % cols) * (cw + gap), y + (i // cols) * (ch + gap)
            tg, dg = f"t{i}", f"d{i}"
            saved = sum(a for a, d in zip(tb["amounts"], tb["done"]) if d)
            fr = min(1, saved / tb["target"])
            box = p.rr(x, yy, x + cw, yy + ch, 26, fill=t["card"], outline=t["line"], width=2, tags=tg)
            p.tx(x + 24, yy + 30, tb["name"][:22], 19, True, anchor="w", tags=tg)
            p.tx(x + 24, yy + 64, f"฿{fmt(saved)} / ฿{fmt(tb['target'])}", 16, anchor="w", fill=t["sub"], tags=tg)
            p.rr(x + 24, yy + 92, x + cw - 24, yy + 104, 6, fill=t["cell"], tags=tg)
            if fr > 0:
                p.rr(x + 24, yy + 92, x + 24 + max(12, (cw - 48) * fr), yy + 104, 6, fill=s.accent, tags=tg)
            p.tx(x + 24, yy + 124, f"{sum(tb['done'])}/{len(tb['done'])} วัน", 14, anchor="w", fill=t["sub"], tags=tg)
            p.tx(x + cw - 24, yy + 124, f"{fr * 100:.0f}%", 15, True, anchor="e", fill=s.accent, tags=tg)
            p.rr(x + cw - 50, yy + 8, x + cw - 8, yy + 50, 10, fill=t["card"], tags=dg)
            p.tx(x + cw - 29, yy + 29, "✕", 16, fill=t["sub"], tags=dg)
            p.tag_bind(tg, "<Button-1>", lambda e, tid=tb["id"]: s.show(lambda pp, ww, hh: s.table_page(pp, ww, hh, tid), 1))
            p.tag_bind(tg, "<Enter>", lambda e, b=box: (p.itemconfig(b, outline=s.accent), p.configure(cursor="hand2")))
            p.tag_bind(tg, "<Leave>", lambda e, b=box: (p.itemconfig(b, outline=t["line"]), p.configure(cursor="")))
            p.click(dg, lambda i=i: s.delete_table(i))
        return y + (-(-len(s.tables) // cols)) * (ch + gap) + 10

    # ---- เครื่องคิดเลข (หน้าต่างลอย ลากได้) ----
    def toggle_calc(s):
        if s.calc_win and s.calc_win.winfo_exists():
            return s.close_calc()
        top = tk.Toplevel(s.root)
        top.overrideredirect(True)
        top.configure(bg=s.t["bg"])
        W, H = S(380), S(590)
        top.geometry(f"{W}x{H}+{s.root.winfo_x() + s.root.winfo_width() - W - S(36)}+{s.root.winfo_y() + S(110)}")
        top.transient(s.root)
        pg = Page(s, top, s.calculator)
        pg.closebtn = pg.nobg = pg.nofx = True
        pg.win = top
        pg.pack(fill="both", expand=True)
        pg.bind("<Button-1>", lambda e: top.focus_force(), add="+")
        top.bind("<Key>", s.calc_key)
        s.calc_win = top
        top.after(60, top.focus_force)

    def close_calc(s):
        if s.calc_win:
            try:
                s.calc_win.destroy()
            except tk.TclError:
                pass
        s.calc_win = s.calc_upd = None

    def calc_key(s, e):
        k, ks = e.char, e.keysym
        m = {"*": "×", "/": "÷", "-": "−", "+": "+", ".": ".", "%": "%", "(": "(", ")": ")"}
        if ks in ("Return", "KP_Enter") or k == "=":
            key = "="
        elif ks == "BackSpace":
            key = "⌫"
        elif ks == "Escape":
            return s.close_calc()
        elif k and k in "cC":
            key = "AC"
        elif k and k in "0123456789":
            key = k
        elif k and k in m:
            key = m[k]
        else:
            return
        calc_press(s.calc, key)
        if s.calc_upd:
            s.calc_upd()

    def calculator(s, p, w, h):
        t, c = s.t, s.calc
        p.create_rectangle(1, 1, p.W - 1, p.H - 1, outline=t["line"], width=S(2))
        p.tx(24, 34, "🧮  เครื่องคิดเลข", 19, True, anchor="w")
        p.button(w - 62, 12, 44, 44, "✕", s.close_calc, "ghost", size=16)
        # จอแสดงผล
        p.rr(16, 68, w - 16, 198, 24, fill=t["card"], outline=t["line"], width=2)
        mm = p.tx(34, 94, "", 14, True, anchor="w", fill=s.accent)
        top = p.tx(w - 34, 94, "", 15, anchor="e", fill=t["sub"])
        main = p.tx(w - 34, 152, "", 42, True, anchor="e")

        def upd():
            tp, mn = calc_display(c)
            size = 42 if len(mn) <= 11 else max(16, int(42 * 11 / len(mn)))
            p.itemconfig(main, text=mn, font=(FONT, -S(size), "bold"))
            p.itemconfig(top, text=tp)
            p.itemconfig(mm, text="M" if c.get("mem") else "")
        s.calc_upd = upd
        upd()

        def press(k):
            calc_press(c, k)
            upd()
        g = 8
        bw, bh = (w - 32 - 4 * g) / 5, 50
        rows = [("MC", "MR", "M+", "M−", "⌫"), ("AC", "(", ")", "%", "÷"), ("x²", "7", "8", "9", "×"),
                ("√", "4", "5", "6", "−"), ("1/x", "1", "2", "3", "+"), ("±", "0", ".", "=")]
        for r, row in enumerate(rows):
            col = 0
            for k in row:
                span = 2 if k == "=" else 1
                if k in OPS + "=":
                    kind, base, size = "primary", None, 24 if k == "=" else 22
                elif k == "AC":
                    kind, base, size = "danger", None, 17
                elif k in "0123456789.":
                    kind, base, size = "ghost", t["cell"], 22
                else:
                    kind, base, size = "ghost", t["line"], 15 if k.startswith("M") else 18
                p.button(16 + col * (bw + g), 214 + r * (bh + g), bw * span + g * (span - 1), bh, k,
                         lambda k=k: press(k), kind, size=size, base=base)
                col += span
        return h

    def delete_table(s, i):
        if messagebox.askyesno("ลบตาราง", f"ต้องการลบ “{s.tables[i]['name']}” ใช่หรือไม่?"):
            del s.tables[i]
            s.persist()
            s.show(s.home, 0)

    # ---- สร้างตาราง ----
    def create(s, p, w, h):
        t = s.t
        s.header(p, w, "สร้างตาราง", back=lambda: s.show(s.home, -1))
        W, H = 500, 580
        x0, y0 = (w - W) / 2, max(100, (h - H) / 2 + 30)
        p.rr(x0, y0, x0 + W, y0 + H, 34, fill=t["card"], outline=t["line"], width=2)
        p.tx(w / 2, y0 + 56, "🐷", 44)
        p.tx(w / 2, y0 + 108, "ตั้งเป้าหมายการออมของคุณ", 22, True)
        for dy, lab, key in ((160, "ชื่อตาราง (ไม่บังคับ)", "name"), (250, "จำนวนเงินต่อวัน (บาท)", "daily"),
                             (340, "จำนวนเงินเป้าหมาย (บาท)", "target")):
            p.tx(x0 + 50, y0 + dy, lab, 15, True, anchor="w", fill=t["sub"])
            p.entry(key, x0 + 50, y0 + dy + 18, W - 100, 54)
        pv = p.tx(w / 2, y0 + 446, "", 16, True, fill=t["sub"], tags="pv")

        def parse(v):
            try:
                x = float(v.replace(",", "").strip())
                return x if x > 0 else None
            except ValueError:
                return None

        def check():
            d, g = parse(p.vars["daily"].get()), parse(p.vars["target"].get())
            if not (d and g):
                return None, "กรอกจำนวนเงินต่อวัน และเป้าหมาย", t["sub"]
            if d > g:
                return None, "เงินต่อวันต้องไม่มากกว่าเป้าหมาย", "#ff6b6b"
            n = math.ceil(g / d - 1e-9)
            if n > MAX_DAYS:
                return None, f"จำนวนวันมากเกินไป (สูงสุด {MAX_DAYS:,} วัน)", "#ff6b6b"
            return (d, g, n), f"ใช้เวลาประมาณ {n:,} วัน ✨", s.accent

        def upd():
            _, m, c = check()
            p.itemconfig(pv, text=m, fill=c)
        p.on_change = upd
        upd()

        def shake():
            st = {"o": 0}

            def fn(k):
                off = math.sin(k * 20) * 12 * (1 - k) * SC
                for it in p.find_all():
                    if "bg" not in p.gettags(it):
                        p.move(it, off - st["o"], 0)
                st["o"] = off
            s.tween(380, fn)

        def make(*_):
            r = check()[0]
            if not r:
                return shake()
            d, g, n = r
            amounts = [num(d)] * (n - 1) + [num(round(g - d * (n - 1), 2))]
            tb = dict(id=uuid.uuid4().hex[:8], name=p.vars["name"].get().strip() or f"เป้า {fmt(g)} บาท",
                      daily=num(d), target=num(g), amounts=amounts, done=[False] * n, created=time.time())
            s.tables.append(tb)
            s.persist()
            s.show(lambda pp, ww, hh: s.table_page(pp, ww, hh, tb["id"]), 1)
        p.button(x0 + 90, y0 + 482, 320, 58, "สร้างตารางเก็บเงิน", make, size=18)
        for e in p.ents.values():
            e.bind("<Return>", make)
        if "daily" in p.ents and not p.st.get("focused"):
            p.st["focused"] = True
            p.ents["daily"].focus_set()
        return y0 + H + 30

    # ---- หน้าตารางเก็บเงิน ----
    def table_page(s, p, w, h, tid):
        tb = next((x for x in s.tables if x["id"] == tid), None)
        if not tb:
            return s.home(p, w, h)
        t, n = s.t, len(tb["amounts"])

        def totals():
            return sum(a for a, d in zip(tb["amounts"], tb["done"]) if d), sum(tb["done"])

        def reset():
            if messagebox.askyesno("รีเซ็ต", "ล้างเครื่องหมายทั้งหมดในตารางนี้ใช่หรือไม่?"):
                tb["done"] = [False] * n
                s.persist()
                s.show(lambda pp, ww, hh: s.table_page(pp, ww, hh, tid), 0)
        y = s.header(p, w, tb["name"][:22], back=lambda: s.show(s.home, -1), size=28)
        p.button(w - 126, 22, 98, 44, "รีเซ็ต", reset, "ghost", size=15)
        if "f" not in p.st:
            p.st["f"] = min(1, totals()[0] / tb["target"])
        py = y

        def prog():
            p.delete("prog")
            saved, nd = totals()
            x1, x2 = 32, w - 32
            p.rr(x1, py, x2, py + 124, 26, fill=t["card"], outline=t["line"], width=2, tags="prog")
            p.tx(x1 + 28, py + 36, "฿" + fmt(saved), 34, True, anchor="w", tags="prog")
            p.tx(x2 - 28, py + 36, f"เป้าหมาย ฿{fmt(tb['target'])}", 16, anchor="e", fill=t["sub"], tags="prog")
            p.rr(x1 + 28, py + 66, x2 - 28, py + 82, 8, fill=t["cell"], tags="prog")
            fw = (x2 - x1 - 56) * p.st["f"]
            if fw >= 1:
                p.rr(x1 + 28, py + 66, x1 + 28 + max(fw, 16), py + 82, 8, fill=s.accent, tags="prog")
            p.tx(x1 + 28, py + 102, f"เก็บแล้ว {totals()[1]}/{n} วัน", 15, anchor="w", fill=t["sub"], tags="prog")
            p.tx(x2 - 28, py + 102, "🎉 ครบเป้าหมายแล้ว!" if nd == n else f"{p.st['f'] * 100:.0f}%", 15, True,
                 anchor="e", fill=s.accent, tags="prog")
        prog()

        def refresh():
            a, b = p.st["f"], min(1, totals()[0] / tb["target"])

            def fn(k):
                p.st["f"] = a + (b - a) * k
                prog()
            s.tween(320, fn, key=(p, "prog"))

        rect, txt, idx = [], [], []

        def toggle(i):
            on = tb["done"][i] = not tb["done"][i]
            s.persist()
            c0, c1 = (t["cell"], s.accent) if on else (s.accent, t["cell"])
            t0, t1 = (t["fg"], "#ffffff") if on else ("#ffffff", t["fg"])
            lt = mix(s.accent, "#ffffff", .6)
            i0, i1 = (t["sub"], lt) if on else (lt, t["sub"])
            p.itemconfig(txt[i], text=("✓ " if on else "") + fmt(tb["amounts"][i]))
            p.itemconfig(rect[i], outline=s.accent if on else t["line"])
            s.tween(240, lambda k: (p.itemconfig(rect[i], fill=mix(c0, c1, k)), p.itemconfig(txt[i], fill=mix(t0, t1, k)),
                                    p.itemconfig(idx[i], fill=mix(i0, i1, k))), key=(p, i))
            refresh()

        gy = py + 124 + 22
        cw, ch, gap = 118, 52, 12
        cols = max(1, int((w - 64 + gap) // (cw + gap)))
        x0 = max(32, (w - (cols * (cw + gap) - gap)) / 2)
        rad = {"pill": ch / 2, "round": 12, "square": 0}[s.cfg["shape"]]
        for i, a in enumerate(tb["amounts"]):
            on = tb["done"][i]
            x, yy = x0 + (i % cols) * (cw + gap), gy + (i // cols) * (ch + gap)
            tg = f"c{i}"
            rect.append(p.rr(x, yy, x + cw, yy + ch, rad, tags=tg, width=2,
                             fill=s.accent if on else t["cell"], outline=s.accent if on else t["line"]))
            idx.append(p.tx(x + 17, yy + ch / 2, str(i + 1), 11, anchor="w", tags=tg,
                            fill=mix(s.accent, "#ffffff", .6) if on else t["sub"]))
            txt.append(p.tx(x + cw / 2 + 9, yy + ch / 2, ("✓ " if on else "") + fmt(a), 18, True, tags=tg,
                            fill="#ffffff" if on else t["fg"]))
            p.tag_bind(tg, "<Button-1>", lambda e, i=i: toggle(i))
            p.tag_bind(tg, "<Enter>", lambda e, i=i: (p.configure(cursor="hand2"), p.itemconfig(rect[i], outline=s.accent)))
            p.tag_bind(tg, "<Leave>", lambda e, i=i: (p.configure(cursor=""),
                       p.itemconfig(rect[i], outline=s.accent if tb["done"][i] else t["line"])))
        return gy + (-(-n // cols)) * (ch + gap) + 16

    # ---- ตั้งค่า ----
    def settings(s, p, w, h):
        t, cfg = s.t, s.cfg
        y = s.header(p, w, "ตั้งค่า", back=lambda: s.show(s.home, -1))
        x0 = max(32, (w - 740) / 2)

        def sec(title):
            nonlocal y
            y += 14
            p.tx(x0, y + 10, title, 17, True, anchor="w", fill=t["sub"])
            y += 36

        sec("ธีม")
        for k, (key, th) in enumerate(THEMES.items()):
            x, tg = x0 + k * 136, f"th{k}"
            sel = cfg["theme"] == key
            p.rr(x, y, x + 126, y + 80, 18, fill=th["bg"], outline=s.accent if sel else t["line"], width=3 if sel else 1, tags=tg)
            p.rr(x + 16, y + 14, x + 110, y + 40, 10, fill=th["card"], tags=tg)
            p.tx(x + 63, y + 60, th["name"], 14, True, fill=th["fg"], tags=tg)
            p.click(tg, lambda key=key: s.set_cfg(theme=key, bg=None, bg_image=None if cfg["bg"] else cfg["bg_image"]))
        y += 80

        sec("เอฟเฟกต์พื้นหลัง  •  " + FX_NAME.get(cfg["theme"], ""))
        for k, (lab, v) in enumerate((("ปิด", 0), ("น้อย", 1), ("กลาง", 2), ("มาก", 3))):
            p.button(x0 + k * 106, y, 96, 42, lab, lambda v=v: s.set_cfg(fx=v), size=14,
                     kind="primary" if cfg["fx"] == v else "ghost")
        y += 42

        sec("สีหลัก")
        for k, ac in enumerate(ACCENTS):
            tg = f"ac{k}"
            x = x0 + k * 48
            p.create_oval(S(x), S(y), S(x + 38), S(y + 38), fill=ac, width=S(3), tags=tg,
                          outline=t["fg"] if ac == s.accent else ac)
            p.click(tg, lambda a=ac: s.set_cfg(accent=a))

        def pick(key, cur, **extra):
            res = colorchooser.askcolor(color=cur, title="เลือกสี")[1]
            if res:
                s.set_cfg(**{key: res}, **extra)
        p.button(x0 + len(ACCENTS) * 48 + 10, y - 1, 140, 40, "เลือกสีเอง", lambda: pick("accent", s.accent), "ghost", size=14)
        y += 40

        sec("พื้นหลัง")

        def choose_image():
            if not Image:
                messagebox.showinfo("ต้องติดตั้ง Pillow", "การใช้รูปพื้นหลังต้องติดตั้ง Pillow ก่อน\nเปิด Command Prompt แล้วพิมพ์:\n\npip install pillow")
                return
            src = filedialog.askopenfilename(title="เลือกรูปพื้นหลัง",
                                             filetypes=[("รูปภาพ", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("ทั้งหมด", "*.*")])
            if not src:
                return
            try:
                Image.open(src).verify()
                name = f"background_{int(time.time())}{os.path.splitext(src)[1].lower()}"
                shutil.copy2(src, os.path.join(ROOT_DIR, name))
            except Exception as ex:
                messagebox.showerror("เปิดรูปไม่ได้", str(ex))
                return
            old = cfg.get("bg_image")
            if old:
                try:
                    os.remove(os.path.join(ROOT_DIR, old))
                except OSError:
                    pass
            s.set_cfg(bg_image=name)
        p.button(x0, y, 200, 46, "🖼  เลือกรูปภาพ", choose_image, size=15)
        p.button(x0 + 212, y, 170, 46, "สีพื้นหลัง", lambda: pick("bg", t["bg"], bg_image=None), "ghost", size=15)
        p.button(x0 + 394, y, 170, 46, "ค่าตามธีม", lambda: s.set_cfg(bg=None, bg_image=None), "ghost", size=15)
        y += 46
        if cfg["bg_image"]:
            y += 16
            p.tx(x0, y + 20, "ความมืดของรูป", 15, anchor="w", fill=t["sub"])
            for k, (lab, v) in enumerate((("สว่าง", 0.0), ("กลาง", 0.35), ("มืด", 0.6))):
                p.button(x0 + 150 + k * 100, y, 90, 40, lab, lambda v=v: s.set_cfg(dim=v), size=14,
                         kind="primary" if abs(cfg["dim"] - v) < .01 else "ghost")
            p.button(x0 + 470, y, 140, 40, "เบลอ: เปิด" if cfg["blur"] else "เบลอ: ปิด",
                     lambda: s.set_cfg(blur=not cfg["blur"]), size=14, kind="primary" if cfg["blur"] else "ghost")
            y += 40

        sec("รูปทรงช่องในตาราง")
        for k, (key, lab) in enumerate((("pill", "แคปซูล"), ("round", "มนเหลี่ยม"), ("square", "เหลี่ยม"))):
            p.button(x0 + k * 126, y, 116, 42, lab, lambda key=key: s.set_cfg(shape=key), size=14,
                     kind="primary" if cfg["shape"] == key else "ghost")
        y += 42

        sec("เอฟเฟกต์การเคลื่อนไหว")
        tr = p.rr(x0, y, x0 + 64, y + 34, 17, fill=mix(t["cell"], s.accent, 1 if cfg["anim"] else 0), outline=t["line"], tags="sw")
        kn = p.create_oval(0, 0, 0, 0, fill="#ffffff", outline="", tags="sw")

        def knob(pr):
            cx = x0 + 17 + 30 * pr
            p.coords(kn, S(cx - 13), S(y + 4), S(cx + 13), S(y + 30))
            p.itemconfig(tr, fill=mix(t["cell"], s.accent, pr))
        knob(1 if cfg["anim"] else 0)
        p.tx(x0 + 84, y + 17, "เปิดแอนิเมชัน (เปลี่ยนหน้า / ปุ่ม / ช่องตาราง)", 16, anchor="w")

        def tog():
            old = cfg["anim"]
            cfg["anim"] = not old
            save(CFG_FILE, cfg)
            s.tween(200, lambda k: knob(1 - k if old else k))
            knob(0 if old else 1) if not cfg["anim"] else None
        p.click("sw", tog)
        y += 34

        sec("ข้อมูล")

        def open_dir():
            os.makedirs(ROOT_DIR, exist_ok=True)
            try:
                if sys.platform.startswith("win"):
                    os.startfile(ROOT_DIR)
                else:
                    subprocess.Popen(["xdg-open", ROOT_DIR])
            except Exception:
                pass
        p.button(x0, y, 210, 42, "เปิดโฟลเดอร์ข้อมูล", open_dir, "ghost", size=14)
        p.tx(x0 + 226, y + 21, ROOT_DIR, 13, anchor="w", fill=t["sub"])
        return y + 70


if __name__ == "__main__":
    App().root.mainloop()