#!/usr/bin/env python3
"""
main.py — Bans BotTools | Habbo Bot Manager (tkinter + web.py)
Uso: python main.py
"""

import tkinter as tk
from tkinter import ttk, filedialog
import threading, json, time, os, random, webbrowser, configparser

import state
import web as _web
from bot_instance import BotInstance
from habbo_client import HabboClientGUI
from sso_retriever import get_sso_ticket, check_session
import constants as const

WEB_PORT = 5000
CFG_FILE = 'habbonet_cfg.ini'

# =============================================================================
# THEME
# =============================================================================
BG       = '#c4c0b0'
BG2      = '#b8b4a4'
BG_CARD  = '#F2F2EB'
BG_INP   = '#e8e4d8'
BG_BTN   = '#30728C'
BG_ACT   = '#1d5a72'
FG       = '#1a1a1a'
FG_M     = '#4a6a7a'
CY       = '#30728C'
GR       = '#1a7a3a'
RD       = '#BF2C2C'
OR       = '#b85c00'
PU       = '#6633aa'
BL       = '#1155aa'
YE       = '#8a7200'

HABBO_HEADER = '#30728C'
HABBO_BORDER = '#3C88A6'
CREAM        = '#F2F2EB'

FMAIN  = ('Segoe UI', 9)
FBOLD  = ('Segoe UI', 9, 'bold')
FSMALL = ('Segoe UI', 8)
FTITLE = ('Segoe UI', 13, 'bold')
FHEAD  = ('Segoe UI', 10, 'bold')
FMONO  = ('Consolas', 8)

TAG_COLORS = {
    'connected':  GR,
    'banned':     RD,
    'failed':     OR,
    'preparing':  '#1a5c9a',
    'connecting': BL,
    'expired':    '#cc44aa',
    'other':      FG_M,
}

# =============================================================================
# WIDGET HELPERS
# =============================================================================

def _bg(w):
    try: return w.cget('bg')
    except: return BG

def _hl(h, n=22):
    try:
        r, g, b = int(h[1:3],16), int(h[3:5],16), int(h[5:7],16)
        return f'#{min(255,r+n):02x}{min(255,g+n):02x}{min(255,b+n):02x}'
    except: return h

def lbl(p, t='', fg=FG, bg=None, f=None, **kw):
    return tk.Label(p, text=t, fg=fg, bg=bg or _bg(p), font=f or FMAIN, **kw)

def frm(p, bg=None, **kw):
    return tk.Frame(p, bg=bg or _bg(p), **kw)

def inp(p, w=18, **kw):
    return tk.Entry(p, bg=BG_INP, fg=FG, insertbackground=CY,
                    relief='flat', bd=4, font=FMAIN, width=w, **kw)

def btn(p, t, bg=BG_BTN, fg=FG, cmd=None, **kw):
    """Button helper — padx/pady in kw override the defaults (9/5)."""
    kw.setdefault('padx', 9)
    kw.setdefault('pady', 5)
    return tk.Button(p, text=t, bg=bg, fg=fg,
                     activebackground=_hl(bg), activeforeground=fg,
                     relief='flat', bd=0, font=FBOLD,
                     cursor='hand2', command=cmd, **kw)

def sep(p, color='#1a1a30'):
    return tk.Frame(p, bg=color, height=1)

def section(p, title):
    f = frm(p, bg=CREAM)
    f.configure(highlightthickness=2, highlightbackground='#000000')
    h = tk.Frame(f, bg=HABBO_HEADER, highlightthickness=2, highlightbackground=HABBO_BORDER)
    h.pack(fill='x')
    lbl(h, title, fg='#ffffff', bg=HABBO_HEADER, f=FHEAD).pack(side='left', padx=9, pady=5)
    sep(f, '#000000').pack(fill='x')
    return f

def placeholder(entry, text):
    entry.insert(0, text)
    entry.config(fg=FG_M)
    def on_in(e):
        if entry.get() == text: entry.delete(0, 'end'); entry.config(fg=FG)
    def on_out(e):
        if not entry.get(): entry.insert(0, text); entry.config(fg=FG_M)
    entry.bind('<FocusIn>',  on_in)
    entry.bind('<FocusOut>', on_out)

def _setup_treeview_style():
    s = ttk.Style(); s.theme_use('clam')
    s.configure('Dark.Treeview', background=CREAM, foreground=FG,
                 fieldbackground=CREAM, rowheight=24, borderwidth=0, font=FSMALL)
    s.configure('Dark.Treeview.Heading', background=HABBO_HEADER,
                 foreground='#ffffff', font=FHEAD, relief='flat')
    s.map('Dark.Treeview', background=[('selected', '#c4dff0')])


# =============================================================================
# CONFIG
# =============================================================================

class AppConfig:
    def __init__(self):
        self._cfg  = configparser.ConfigParser()
        self._path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CFG_FILE)
        self._cfg.read(self._path, encoding='utf-8')

    def get(self, section, key, fallback=''):
        return self._cfg.get(section, key, fallback=fallback)

    def set(self, section, key, value):
        if not self._cfg.has_section(section): self._cfg.add_section(section)
        self._cfg.set(section, key, str(value))
        try:
            with open(self._path, 'w', encoding='utf-8') as f: self._cfg.write(f)
        except Exception: pass


# =============================================================================
# DIALOG
# =============================================================================

class HabboDialog(tk.Toplevel):
    def __init__(self, parent, title='', message='', icon='ℹ'):
        super().__init__(parent)
        self.transient(parent); self.grab_set()
        self.resizable(False, False); self.configure(bg=CREAM); self.title(title)
        hd = tk.Frame(self, bg=HABBO_HEADER); hd.pack(fill='x')
        lbl(hd, f'  {icon}  {title}', fg='#fff', bg=HABBO_HEADER, f=FHEAD).pack(side='left', padx=8, pady=7)
        sep(self, '#000').pack(fill='x')
        bd = frm(self, bg=CREAM); bd.pack(padx=20, pady=14)
        lbl(bd, message, fg=FG, bg=CREAM, f=FMAIN, justify='left', wraplength=340).pack()
        sep(self, '#000').pack(fill='x')
        ft = frm(self, bg=CREAM); ft.pack(fill='x', padx=14, pady=8)
        btn(ft, 'OK', bg=BG_BTN, fg='#fff', cmd=self.destroy).pack(side='right')
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f'+{px}+{py}'); self.wait_window()

def habbo_msg(parent, title, message, icon='ℹ'):
    HabboDialog(parent, title, message, icon)


# =============================================================================
# STATUS BAR
# =============================================================================

class StatusBar(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=HABBO_HEADER, height=22, **kw)
        self._msg  = tk.Label(self, text='Ready', fg='#d0eeff',
                               bg=HABBO_HEADER, font=FSMALL, anchor='w')
        self._msg.pack(side='left', padx=8, fill='x', expand=True)
        self._stat = tk.Label(self, text='', fg='#90d8b0',
                               bg=HABBO_HEADER, font=FSMALL, anchor='e')
        self._stat.pack(side='right', padx=8)
        self._job = None

    def msg(self, text, color='#d0eeff', timeout=4000):
        self._msg.config(text=text, fg=color)
        if self._job: self.after_cancel(self._job)
        self._job = self.after(timeout, lambda: self._msg.config(text='Ready', fg='#d0eeff'))

    def ok(self, text):   self.msg(f'✓  {text}', '#90d8b0')
    def err(self, text):  self.msg(f'✗  {text}', '#ff7070')
    def info(self, text): self.msg(f'ℹ  {text}', '#d0eeff')

    def update_counts(self, connected, total, proxies):
        self._stat.config(
            text=f'Bots: {connected}/{total}   Proxies: {proxies}'
                 f'   F5=Refresh  Ctrl+A=All  Del=Disc  Enter=Conn')


# =============================================================================
# NET CONTROLLER
# =============================================================================

class NetController:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('Bans BotTools')
        self.root.configure(bg=BG)

        self._cfg = AppConfig()
        self.root.geometry(self._cfg.get('window', 'geometry', '1060x680'))
        self.root.minsize(860, 560)
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        _setup_treeview_style()

        self.bots    = state.bots
        self.proxies = state.proxies

        self._auto_rec        = tk.BooleanVar(value=self._cfg.get('settings','auto_rec','1')=='1')
        self._anti_admin      = tk.BooleanVar(value=self._cfg.get('settings','anti_admin','1')=='1')
        self._auto_refresh_var = tk.BooleanVar(value=self._cfg.get('settings','auto_refresh','1')=='1')
        self._split_n    = tk.StringVar(value=self._cfg.get('settings','split_n','3'))
        self._target_var = tk.StringVar(value='All Connected')
        self._hotel_var  = tk.StringVar(value=self._cfg.get('settings','hotel','habbo.com'))
        self._rec_delay  = tk.StringVar(value=self._cfg.get('settings','rec_delay','30'))
        self._filter_var = tk.StringVar()
        self._sel_pg     = tk.StringVar(value='DIRECT')

        self._spammer_on = False
        self._spam_count = 0
        self._troll_on   = False
        self._nav_rooms  = []
        self._nav_btns   = {}
        self._tab_btns   = {}
        self._pages      = {}
        self._tab_frames = {}
        self._cur_page   = None
        self._cur_tab    = None
        self._bot_proxy_groups: dict = {}
        self._selected_grp = None
        self._ui_ready = False   # guard: prevents refresh before UI is built

        self._hotel_var.trace_add('write', self._on_hotel_change)
        self._filter_var.trace_add('write', lambda *_: self._safe_refresh())

        self._build()
        self._ui_ready = True
        self._auto_load()
        self._start_web_server()
        self._start_auto_reconnect()
        self._fetch_headers_async()
        self._schedule_refresh()
        self.show_page('dashboard')
        self.show_tab('ACTIONS')
        self._bind_shortcuts()

    # ─── close ───────────────────────────────────────────────────────────────

    def _on_close(self):
        self._cfg.set('window', 'geometry', self.root.geometry())
        self._cfg.set('settings', 'auto_rec',     '1' if self._auto_rec.get()        else '0')
        self._cfg.set('settings', 'anti_admin',   '1' if self._anti_admin.get()      else '0')
        self._cfg.set('settings', 'auto_refresh', '1' if self._auto_refresh_var.get() else '0')
        self._cfg.set('settings', 'split_n',    self._split_n.get())
        self._cfg.set('settings', 'hotel',      self._hotel_var.get())
        self._cfg.set('settings', 'rec_delay',  self._rec_delay.get())
        self.root.destroy()

    def _safe_refresh(self):
        if self._ui_ready: self._refresh_ui()

    # ─── shortcuts ───────────────────────────────────────────────────────────

    def _bind_shortcuts(self):
        self.root.bind('<F5>',        lambda e: self._refresh_ui())
        self.root.bind('<Control-a>', lambda e: self._select_all())
        self.root.bind('<Control-A>', lambda e: self._select_all())
        self.root.bind('<Delete>',    lambda e: self._disc_sel())
        self.root.bind('<Return>',    lambda e: self._conn_sel())
        self.root.bind('<Control-s>', lambda e: self._save_accounts_json())
        self.root.bind('<Control-S>', lambda e: self._save_accounts_json())

    def _select_all(self):
        tree = self._get_active_tree()
        if tree: tree.selection_set(tree.get_children())

    # =========================================================================
    # BUILD
    # =========================================================================

    def _build(self):
        sidebar = frm(self.root, bg=BG2, width=160)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        main = frm(self.root, bg=BG)
        main.pack(side='left', fill='both', expand=True)

        self._statusbar = StatusBar(self.root)
        self._statusbar.pack(side='bottom', fill='x')

        self._page_host = frm(main, bg=BG)
        self._page_host.pack(fill='both', expand=True)

        self._build_topbars(main)
        self._build_tabbar(main)

        self._pages['dashboard'] = self._pg_dashboard()
        self._pages['control']   = self._pg_control()
        self._pages['accounts']  = self._pg_accounts()
        self._pages['proxies']   = self._pg_proxies()

    def _build_sidebar(self, parent):
        logo = frm(parent, bg=HABBO_HEADER); logo.pack(fill='x')
        lbl(logo, 'BANS', fg='#fff', bg=HABBO_HEADER, f=FTITLE).pack(pady=(8,0))
        lbl(logo, 'BOTTOOLS', fg='#c8eeff', bg=HABBO_HEADER, f=FSMALL).pack(pady=(0,8))
        sep(parent, HABBO_BORDER).pack(fill='x')

        for pid, label in [('dashboard','⊞  Dashboard'),('control','⚙  Control'),
                            ('accounts','👤  Accounts'),('proxies','⬡  Proxies')]:
            b = tk.Button(parent, text=label, bg=BG2, fg=FG_M,
                          activebackground=HABBO_HEADER, activeforeground='#fff',
                          relief='flat', bd=0, padx=12, pady=10,
                          font=FMAIN, cursor='hand2', anchor='w',
                          command=lambda p=pid: self.show_page(p))
            b.pack(fill='x'); self._nav_btns[pid] = b

        sep(parent, HABBO_BORDER).pack(fill='x', pady=(8,0))
        self._side_stat = lbl(parent, '0 / 0 bots', fg=GR, bg=BG2, f=FSMALL)
        self._side_stat.pack(pady=4, padx=8, anchor='w')

        lbl(parent, 'Hotel:', fg=FG_M, bg=BG2, f=FSMALL).pack(padx=8, anchor='w')
        hm = tk.OptionMenu(parent, self._hotel_var, *const.HOTELS.keys())
        hm.config(bg=BG_BTN, fg='#fff', activebackground=BG_ACT,
                  relief='flat', bd=0, font=FSMALL, width=12, highlightthickness=0)
        hm['menu'].config(bg=BG_BTN, fg='#fff', activebackground=BG_ACT, relief='flat')
        hm.pack(padx=6, pady=4, anchor='w')

        sep(parent, HABBO_BORDER).pack(fill='x', pady=4)
        btn(parent, '▶ Connect All', bg='#0a3a18', fg=GR, cmd=self.connect_all).pack(fill='x', padx=6, pady=2)
        btn(parent, '■ Disc. All',   bg='#3a0a0a', fg=RD, cmd=self.disconnect_all).pack(fill='x', padx=6, pady=2)

        sep(parent, HABBO_BORDER).pack(fill='x', pady=(8,0))
        self._web_lbl = lbl(parent, f'WEB :{WEB_PORT}…', fg=OR, bg=BG2, f=FSMALL)
        self._web_lbl.pack(padx=8, pady=4, anchor='w')
        self._web_lbl.bind('<Button-1>', lambda e: webbrowser.open(f'http://localhost:{WEB_PORT}'))

    def _build_topbars(self, parent):
        # ── Dashboard topbar ──────────────────────────────────────────────────
        self._topbar_dash = frm(parent, bg=HABBO_HEADER, height=36)
        self._topbar_dash.pack_propagate(False)

        self._conn_lbl = lbl(self._topbar_dash, 'CONN: 0', fg='#90ffb0', bg=HABBO_HEADER, f=FBOLD)
        self._conn_lbl.pack(side='left', padx=(10,6), pady=6)
        self._disc_lbl = lbl(self._topbar_dash, 'DISC: 0', fg='#ffaaaa', bg=HABBO_HEADER, f=FBOLD)
        self._disc_lbl.pack(side='left', padx=(0,6), pady=6)

        sep(self._topbar_dash, '#3C88A6').pack(side='left', fill='y', pady=6)
        lbl(self._topbar_dash, ' 🔍', fg='#c8eeff', bg=HABBO_HEADER, f=FSMALL).pack(side='left', padx=(4,2))
        fi = tk.Entry(self._topbar_dash, textvariable=self._filter_var,
                       bg='#1d5a72', fg='#c8eeff', insertbackground='#c8eeff',
                       relief='flat', bd=4, font=FSMALL, width=14)
        fi.pack(side='left', padx=(0,6), ipady=2)
        placeholder(fi, 'Filter bots...')

        lbl(self._topbar_dash, 'Group:', fg='#c8eeff', bg=HABBO_HEADER, f=FSMALL).pack(side='left', padx=(4,2))
        self._pg_dash_menu = tk.OptionMenu(self._topbar_dash, self._sel_pg, 'DIRECT')
        self._pg_dash_menu.config(bg='#1d5a72', fg='#c8eeff', activebackground=BG_ACT,
                                   relief='flat', bd=0, font=FSMALL, width=10, highlightthickness=0)
        self._pg_dash_menu['menu'].config(bg='#1d5a72', fg='#c8eeff', activebackground=BG_ACT, relief='flat')
        self._pg_dash_menu.pack(side='left', padx=(0,4))

        btn(self._topbar_dash, 'Assign Sel.', bg=BG_ACT, fg='#c8eeff',
            cmd=self._assign_pg_to_sel, pady=3, padx=6).pack(side='left')

        sep(self._topbar_dash, '#3C88A6').pack(side='left', fill='y', pady=6)
        btn(self._topbar_dash, '▶ Conn', bg='#0a3a18', fg=GR,
            cmd=self._conn_sel, pady=3, padx=6).pack(side='left', padx=(4,2))
        btn(self._topbar_dash, '■ Disc', bg='#3a0a0a', fg=RD,
            cmd=self._disc_sel, pady=3, padx=6).pack(side='left', padx=2)
        btn(self._topbar_dash, '☐ All', bg=BG2, fg=FG,
            cmd=self._select_all, pady=3, padx=6).pack(side='left', padx=2)

        # ── Control topbar ────────────────────────────────────────────────────
        self._topbar_ctrl = frm(parent, bg=HABBO_HEADER, height=36)
        self._topbar_ctrl.pack_propagate(False)

        self._conn_lbl2 = lbl(self._topbar_ctrl, 'CONN: 0', fg='#90ffb0', bg=HABBO_HEADER, f=FBOLD)
        self._conn_lbl2.pack(side='left', padx=(10,6), pady=6)
        self._disc_lbl2 = lbl(self._topbar_ctrl, 'DISC: 0', fg='#ffaaaa', bg=HABBO_HEADER, f=FBOLD)
        self._disc_lbl2.pack(side='left', padx=(0,10), pady=6)

        sep(self._topbar_ctrl, '#3C88A6').pack(side='left', fill='y', pady=6)
        lbl(self._topbar_ctrl, 'Target:', fg='#c8eeff', bg=HABBO_HEADER, f=FSMALL).pack(side='left', padx=(8,4))
        self._target_menu = tk.OptionMenu(self._topbar_ctrl, self._target_var, 'All Connected')
        self._target_menu.config(bg='#1d5a72', fg='#c8eeff', activebackground=BG_ACT,
                                  relief='flat', bd=0, font=FSMALL, width=20, highlightthickness=0)
        self._target_menu['menu'].config(bg='#1d5a72', fg='#c8eeff', activebackground=BG_ACT, relief='flat')
        self._target_menu.pack(side='left', padx=(0,8))

        sep(self._topbar_ctrl, '#3C88A6').pack(side='left', fill='y', pady=6)
        lbl(self._topbar_ctrl, ' Split:', fg='#c8eeff', bg=HABBO_HEADER, f=FSMALL).pack(side='left', padx=(4,2))
        tk.Entry(self._topbar_ctrl, textvariable=self._split_n,
                  bg='#1d5a72', fg='#c8eeff', insertbackground='#c8eeff',
                  relief='flat', bd=4, font=FSMALL, width=3).pack(side='left', padx=(0,8), ipady=1)

        lbl(self._topbar_ctrl, '♻ Auto-Rec:', fg='#c8eeff', bg=HABBO_HEADER, f=FSMALL).pack(side='left')
        tk.Checkbutton(self._topbar_ctrl, variable=self._auto_rec, bg=HABBO_HEADER,
                        activebackground=HABBO_HEADER, selectcolor='#1d5a72', relief='flat').pack(side='left')
        lbl(self._topbar_ctrl, '  🛡 Anti-Admin:', fg='#c8eeff', bg=HABBO_HEADER, f=FSMALL).pack(side='left')
        tk.Checkbutton(self._topbar_ctrl, variable=self._anti_admin, bg=HABBO_HEADER,
                        activebackground=HABBO_HEADER, selectcolor='#1d5a72', relief='flat').pack(side='left')

    def _build_tabbar(self, parent):
        self._tabbar = frm(parent, bg='#1d5a72', height=28)
        self._tabbar.pack_propagate(False)
        for name in ['ACTIONS', 'MOVEMENT', 'ROOM INTEL', 'SPAMMER']:
            b = tk.Button(self._tabbar, text=name, bg='#1d5a72', fg=FG_M,
                          activebackground=HABBO_HEADER, activeforeground='#fff',
                          relief='flat', bd=0, padx=14, pady=5, font=FSMALL, cursor='hand2',
                          command=lambda n=name: self.show_tab(n))
            b.pack(side='left'); self._tab_btns[name] = b

    # =========================================================================
    # PAGES
    # =========================================================================

    def _pg_dashboard(self):
        f = frm(self._page_host, bg=BG)
        s = section(f, 'BOT DASHBOARD')
        s.pack(fill='both', expand=True, padx=10, pady=(8,4))

        cols = ('#', 'STATUS', 'NAME', 'HOTEL', 'PROXY', 'GROUP')
        self._dash_tree = ttk.Treeview(s, columns=cols, show='headings',
                                        style='Dark.Treeview', selectmode='extended')
        _dash_stretch = {'NAME': True, 'PROXY': True}
        for col, w in zip(cols, [35, 100, 160, 110, 120, 90]):
            self._dash_tree.heading(col, text=col)
            self._dash_tree.column(col, width=w, minwidth=w,
                                   stretch=_dash_stretch.get(col, False), anchor='w')
        for tag, color in TAG_COLORS.items():
            self._dash_tree.tag_configure(tag, foreground=color)

        vsb = tk.Scrollbar(s, orient='vertical', command=self._dash_tree.yview,
                            bg=BG_CARD, troughcolor=BG2, width=7, relief='flat')
        self._dash_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y', pady=6, padx=(0,6))
        self._dash_tree.pack(fill='both', expand=True, padx=8, pady=(4,0))

        self._dash_tree.bind('<<TreeviewSelect>>', self._on_bot_select)
        self._dash_tree.bind('<Double-Button-1>',  self._on_bot_dblclick)
        self._dash_tree.bind('<Button-3>',         lambda e: self._show_ctx_menu(e, self._dash_tree))

        # Log panel
        lp = frm(f, bg=CREAM); lp.pack(fill='x', padx=10, pady=(0,6))
        lp.configure(highlightthickness=1, highlightbackground='#000')
        lph = tk.Frame(lp, bg=HABBO_HEADER); lph.pack(fill='x')
        self._log_header_lbl = lbl(lph, '  Log — selecciona un bot', fg='#c8eeff', bg=HABBO_HEADER, f=FSMALL)
        self._log_header_lbl.pack(side='left', pady=3, padx=4)
        btn(lph, '↑ Full Log', bg=HABBO_BORDER, fg='#fff',
            cmd=self._open_log_window_sel, pady=1, padx=6).pack(side='right', padx=4, pady=2)
        btn(lph, '⟳', bg=HABBO_BORDER, fg='#fff',
            cmd=self._on_bot_select, pady=1, padx=6).pack(side='right', padx=2, pady=2)
        self._dash_log = tk.Text(lp, bg='#1a1a1a', fg='#c8e0c8', insertbackground='#fff',
                                  relief='flat', height=6, font=FMONO, bd=4,
                                  highlightthickness=0, state='disabled')
        self._dash_log.tag_config('gr', foreground='#66dd88')
        self._dash_log.tag_config('rd', foreground='#ff6666')
        self._dash_log.tag_config('cy', foreground='#66ccff')
        self._dash_log.tag_config('or', foreground='#ffaa44')
        self._dash_log.pack(fill='x', padx=4, pady=(0,4))
        return f

    def _pg_control(self):
        f = frm(self._page_host, bg=BG)
        area = frm(f, bg=BG); area.pack(fill='both', expand=True)
        for name, builder in [('ACTIONS',    self._tab_actions),
                               ('MOVEMENT',   self._tab_movement),
                               ('ROOM INTEL', self._tab_room_intel),
                               ('SPAMMER',    self._tab_spammer)]:
            self._tab_frames[name] = builder(area)
        return f

    def _tab_actions(self, p):
        f = frm(p, bg=BG)
        left = frm(f, bg=BG); right = frm(f, bg=BG)
        left.pack(side='left', fill='both', expand=True, padx=(10,4), pady=10)
        right.pack(side='left', fill='both', expand=True, padx=(4,10), pady=10)

        # Communication
        com = section(left, 'COMMUNICATION'); com.pack(fill='x', pady=(0,8))
        r1 = frm(com, bg=BG_CARD); r1.pack(fill='x', padx=8, pady=(8,4))
        self._shout_inp = inp(r1, w=28); placeholder(self._shout_inp, 'Shout msg...')
        self._shout_inp.pack(fill='x')
        r2 = frm(com, bg=BG_CARD); r2.pack(fill='x', padx=8, pady=(0,4))
        btn(r2, '📢 SHOUT', bg='#102048', fg=BL, cmd=self._act_shout).pack(side='left', padx=(0,4), fill='x', expand=True)
        btn(r2, '💬 SAY',   bg=BG_BTN,   fg='#fff', cmd=self._act_say).pack(side='left', fill='x', expand=True)
        r3 = frm(com, bg=BG_CARD); r3.pack(fill='x', padx=8, pady=(0,4))
        self._wuser_inp = inp(r3, w=13); placeholder(self._wuser_inp, 'User'); self._wuser_inp.pack(side='left', padx=(0,4))
        self._wmsg_inp  = inp(r3, w=15); placeholder(self._wmsg_inp,  'Msg');  self._wmsg_inp.pack(side='left', fill='x', expand=True)
        r4 = frm(com, bg=BG_CARD); r4.pack(fill='x', padx=8, pady=(0,8))
        btn(r4, '🔒 WHISPER', bg='#281050', fg=PU, cmd=self._act_whisper).pack(fill='x')

        # Identity
        idc = section(left, 'IDENTITY CONTROL'); idc.pack(fill='x')
        r5a = frm(idc, bg=BG_CARD); r5a.pack(fill='x', padx=8, pady=(8,4))
        self._motto_inp = inp(r5a, w=28); placeholder(self._motto_inp, 'New motto...')
        self._motto_inp.pack(fill='x')
        btn(idc, '✏ Set Motto', bg=BG_BTN, fg='#fff', cmd=self._act_motto).pack(fill='x', padx=8, pady=(0,4))
        r5 = frm(idc, bg=BG_CARD); r5.pack(fill='x', padx=8, pady=(4,4))
        lbl(r5, 'Gender:', fg=FG_M, bg=BG_CARD).pack(side='left')
        self._gender_var = tk.StringVar(value='M')
        for v, n in [('M','Male'),('F','Female')]:
            tk.Radiobutton(r5, text=n, variable=self._gender_var, value=v,
                           bg=BG_CARD, fg=FG, selectcolor=CREAM,
                           activebackground=BG_CARD, font=FSMALL).pack(side='left', padx=4)
        r5b = frm(idc, bg=BG_CARD); r5b.pack(fill='x', padx=8, pady=(0,4))
        self._figure_inp = inp(r5b, w=22); placeholder(self._figure_inp, 'Figure code hr-100...')
        self._figure_inp.pack(side='left', fill='x', expand=True, padx=(0,4))
        btn(r5b, 'Apply', bg=BG_ACT, fg='#fff', cmd=self._act_figure).pack(side='left')
        r6 = frm(idc, bg=BG_CARD); r6.pack(fill='x', padx=8, pady=(0,8))
        btn(r6, '⊞ Rand Look', bg=BG_BTN, fg='#fff', cmd=self._act_rand_look).pack(side='left', padx=(0,4), fill='x', expand=True)
        btn(r6, '✎ Rand Nick',  bg=BG_BTN, fg='#fff', cmd=self._act_rand_nick).pack(side='left', fill='x', expand=True)

        # Room
        room = section(right, 'ROOM OPERATIONS'); room.pack(fill='x', pady=(0,8))
        r7 = frm(room, bg=BG_CARD); r7.pack(fill='x', padx=8, pady=(8,4))
        self._room_var = tk.StringVar(value='80257391')
        ri = inp(r7, w=16); ri.config(textvariable=self._room_var); ri.pack(fill='x', expand=True)
        r8 = frm(room, bg=BG_CARD); r8.pack(fill='x', padx=8, pady=(0,8))
        btn(r8, '▶ JOIN',  bg='#0a3a18', fg=GR, cmd=self._act_join).pack(side='left', padx=(0,4), fill='x', expand=True)
        btn(r8, '✖ LEAVE', bg='#3a0a0a', fg=RD, cmd=self._act_leave).pack(side='left')

        # Interaction
        inter = section(right, 'INTERACTION'); inter.pack(fill='x')
        r9 = frm(inter, bg=BG_CARD); r9.pack(fill='x', padx=8, pady=(8,4))
        self._tgt_user_inp = inp(r9, w=26); placeholder(self._tgt_user_inp, 'Target User (Name/ID)')
        self._tgt_user_inp.pack(fill='x')
        r10 = frm(inter, bg=BG_CARD); r10.pack(fill='x', padx=8, pady=(0,4))
        btn(r10, '♥ RESPECT', bg='#102048', fg=BL, cmd=self._act_respect).pack(side='left', padx=(0,3), fill='x', expand=True)
        btn(r10, '+ FRIEND',  bg=BG_BTN,   fg='#fff', cmd=self._act_friend).pack(side='left', padx=(0,3), fill='x', expand=True)
        btn(r10, '⊕ COPY',   bg='#281050', fg=PU, cmd=self._act_copy_looks).pack(side='left', fill='x', expand=True)
        r11 = frm(inter, bg=BG_CARD); r11.pack(fill='x', padx=8, pady=(0,8))
        btn(r11, '⟳ STALK', bg='#3a1a00', fg=OR, cmd=self._act_stalk).pack(side='left', padx=(0,3), fill='x', expand=True)
        btn(r11, '■ STOP',  bg=BG_BTN,   fg=FG_M, cmd=self._act_stop_all).pack(side='left', fill='x', expand=True)
        return f

    def _tab_movement(self, p):
        f = frm(p, bg=BG)
        left = frm(f, bg=BG); right = frm(f, bg=BG)
        left.pack(side='left', fill='both', expand=True, padx=(10,4), pady=10)
        right.pack(side='left', fill='both', expand=True, padx=(4,10), pady=10)

        mv = section(left, 'WALK TO COORDINATES'); mv.pack(fill='x', pady=(0,8))
        r1 = frm(mv, bg=BG_CARD); r1.pack(fill='x', padx=8, pady=(8,4))
        lbl(r1, 'X:', fg=CY, bg=BG_CARD).pack(side='left')
        self._wx = inp(r1, w=5); self._wx.insert(0,'5'); self._wx.pack(side='left', padx=(2,8))
        lbl(r1, 'Y:', fg=CY, bg=BG_CARD).pack(side='left')
        self._wy = inp(r1, w=5); self._wy.insert(0,'5'); self._wy.pack(side='left', padx=(2,8))
        btn(r1, 'WALK', bg='#102040', fg=BL, cmd=self._act_walk).pack(side='left')
        r2 = frm(mv, bg=BG_CARD); r2.pack(fill='x', padx=8, pady=(0,8))
        btn(r2, '↻ Random Walk', bg='#0a3a18', fg=GR, cmd=self._act_random_walk).pack(side='left', padx=(0,4), fill='x', expand=True)
        btn(r2, '■ Stop Walk',   bg='#3a0a0a', fg=RD, cmd=self._act_stop_walk).pack(side='left', fill='x', expand=True)

        dp = section(left, 'DANCE & POSTURE'); dp.pack(fill='x')
        r3 = frm(dp, bg=BG_CARD); r3.pack(fill='x', padx=8, pady=(8,4))
        lbl(r3, 'Dance:', fg=FG_M, bg=BG_CARD).pack(side='left')
        self._dance_var = tk.StringVar(value='1')
        for val, name in [('0','Stop'),('1','Normal'),('2','Pogo'),('3','Duck'),('4','Rollie')]:
            tk.Radiobutton(r3, text=name, variable=self._dance_var, value=val,
                           bg=BG_CARD, fg=FG, selectcolor=CREAM,
                           activebackground=BG_CARD, font=FSMALL,
                           indicatoron=False, relief='flat',
                           padx=5, pady=4, cursor='hand2').pack(side='left', padx=2)
        r4 = frm(dp, bg=BG_CARD); r4.pack(fill='x', padx=8, pady=(4,8))
        btn(r4, '♫ Dance', bg='#1a0a40', fg=PU, cmd=self._act_dance).pack(side='left', padx=(0,4), fill='x', expand=True)
        btn(r4, 'Sit',     bg=BG_BTN, fg='#fff', cmd=lambda: self._act_posture(1)).pack(side='left', padx=(0,4), fill='x', expand=True)
        btn(r4, 'Stand',   bg=BG_BTN, fg='#fff', cmd=lambda: self._act_posture(0)).pack(side='left', fill='x', expand=True)

        sg = section(right, 'SIGN & EFFECTS'); sg.pack(fill='x')
        r5 = frm(sg, bg=BG_CARD); r5.pack(fill='x', padx=8, pady=(8,4))
        lbl(r5, 'Sign (0-14):', fg=FG_M, bg=BG_CARD).pack(side='left')
        self._sign_var = tk.StringVar(value='1')
        _si = inp(r5, w=4); _si.config(textvariable=self._sign_var); _si.pack(side='left', padx=6)
        btn(r5, 'Show', bg='#282a00', fg=YE, cmd=self._act_sign).pack(side='left')
        r6 = frm(sg, bg=BG_CARD); r6.pack(fill='x', padx=8, pady=(0,8))
        lbl(r6, 'Effect ID:', fg=FG_M, bg=BG_CARD).pack(side='left')
        self._eff_var = tk.StringVar(value='1')
        _ei = inp(r6, w=4); _ei.config(textvariable=self._eff_var); _ei.pack(side='left', padx=6)
        btn(r6, 'Enable', bg='#1a0a40', fg=PU, cmd=self._act_effect).pack(side='left')
        return f

    def _tab_room_intel(self, p):
        f = frm(p, bg=BG)
        left = frm(f, bg=BG); right = frm(f, bg=BG)
        left.pack(side='left', fill='both', expand=True, padx=(10,4), pady=10)
        right.pack(side='left', fill='both', expand=True, padx=(4,10), pady=10)

        nav = section(left, 'NAVIGATOR'); nav.pack(fill='both', expand=True)
        r1 = frm(nav, bg=BG_CARD); r1.pack(fill='x', padx=8, pady=(8,4))
        self._nav_cat = tk.StringVar(value='popular')
        nm = tk.OptionMenu(r1, self._nav_cat, 'popular','official','hotel_view','myworld_view')
        nm.config(bg=BG_BTN, fg='#fff', activebackground=BG_ACT,
                  relief='flat', bd=0, font=FSMALL, width=11, highlightthickness=0)
        nm['menu'].config(bg=BG_BTN, fg='#fff', activebackground=BG_ACT, relief='flat')
        nm.pack(side='left', padx=(0,4))
        self._nav_search = inp(r1, w=16); placeholder(self._nav_search, 'Search...')
        self._nav_search.pack(side='left', fill='x', expand=True)
        r1b = frm(nav, bg=BG_CARD); r1b.pack(fill='x', padx=8, pady=(0,4))
        btn(r1b, '⌕ FETCH', bg='#0a3a18', fg=GR, cmd=self._act_nav_fetch).pack(fill='x')
        self._nav_lb = tk.Listbox(nav, bg=BG_INP, fg=FG, selectbackground='#c4dff0',
                                   selectforeground=FG, relief='flat', bd=0, font=FSMALL,
                                   activestyle='none', highlightthickness=0)
        self._nav_lb.pack(fill='both', expand=True, padx=8, pady=(0,8))
        self._nav_lb.bind('<Double-Button-1>', self._on_nav_dbl)

        me = section(right, 'MAP & ENTITIES'); me.pack(fill='both', expand=True)
        r2 = frm(me, bg=BG_CARD); r2.pack(fill='x', padx=8, pady=(8,4))
        btn(r2, '↺ RELOAD', bg='#102040', fg=BL, cmd=self._act_join).pack(fill='x')
        r3 = frm(me, bg=BG_CARD); r3.pack(fill='x', padx=8, pady=(0,4))
        self._troll_inp = inp(r3, w=22); placeholder(self._troll_inp, 'Troll sentence')
        self._troll_inp.pack(side='left', fill='x', expand=True, padx=(0,4))
        self._troll_btn = btn(r3, '●', bg='#3a1a00', fg=OR, cmd=self._toggle_troll); self._troll_btn.pack(side='left')
        r4 = frm(me, bg=BG_CARD); r4.pack(fill='x', padx=8, pady=(0,4))
        btn(r4, '⊙ SCAN USERS', bg='#102040', fg=BL, cmd=self._act_scan).pack(fill='x')
        lbl(me, 'Entities in Room:', fg=FG_M, bg=BG_CARD, f=FSMALL).pack(anchor='w', padx=8)
        self._entities_lb = tk.Listbox(me, bg=BG_INP, fg=FG, selectbackground='#c4dff0',
                                        selectforeground=FG, relief='flat', bd=0, font=FSMALL,
                                        activestyle='none', highlightthickness=0, height=7)
        self._entities_lb.pack(fill='both', expand=True, padx=8, pady=(0,8))
        return f

    def _tab_spammer(self, p):
        f = frm(p, bg=BG)
        left = frm(f, bg=BG); right = frm(f, bg=BG)
        left.pack(side='left', fill='both', expand=True, padx=(10,4), pady=10)
        right.pack(side='left', fill='both', expand=True, padx=(4,10), pady=10)

        sp = section(left, 'SPAM CONFIGURATION'); sp.pack(fill='x', pady=(0,8))
        lbl(sp, 'Messages (one per line = random pick):', fg=FG_M, bg=BG_CARD, f=FSMALL).pack(anchor='w', padx=8, pady=(8,2))
        self._spam_msg = tk.Text(sp, bg=BG_INP, fg=FG, insertbackground=CY,
                                  relief='flat', height=5, font=FMAIN, bd=4, highlightthickness=0)
        self._spam_msg.pack(fill='x', padx=8, pady=(0,4))
        r1 = frm(sp, bg=BG_CARD); r1.pack(fill='x', padx=8, pady=(0,4))
        lbl(r1, 'Interval (s):', fg=FG_M, bg=BG_CARD).pack(side='left')
        self._spam_ivl = tk.StringVar(value='5')
        iv = inp(r1, w=5); iv.config(textvariable=self._spam_ivl); iv.pack(side='left', padx=6)
        lbl(r1, 'Style (-1=rand):', fg=FG_M, bg=BG_CARD).pack(side='left')
        self._spam_style = tk.StringVar(value='-1')
        st = inp(r1, w=4); st.config(textvariable=self._spam_style); st.pack(side='left', padx=4)
        r2 = frm(sp, bg=BG_CARD); r2.pack(fill='x', padx=8, pady=(0,8))
        btn(r2, '▶ START', bg='#0a3a18', fg=GR, cmd=self._spam_start).pack(side='left', padx=(0,4), fill='x', expand=True)
        btn(r2, '■ STOP',  bg='#3a0a0a', fg=RD, cmd=self._spam_stop).pack(side='left', fill='x', expand=True)
        r3 = frm(sp, bg=BG_CARD); r3.pack(fill='x', padx=8, pady=(0,8))
        self._spam_cnt_lbl    = lbl(r3, 'Sent: 0', fg=GR, bg=BG_CARD); self._spam_cnt_lbl.pack(side='left')
        self._spam_status_lbl = lbl(r3, '  ■ STOPPED', fg=RD, bg=BG_CARD, f=FBOLD); self._spam_status_lbl.pack(side='left')

        tips = section(right, 'VARIABLES'); tips.pack(fill='x', pady=(0,8))
        for var, desc in [('%nick%','Username del bot'),('%index%','Índice del bot'),
                          ('%room%','Room ID actual'),('%count%','Mensajes enviados')]:
            rv = frm(tips, bg=BG_CARD); rv.pack(fill='x', padx=8, pady=2)
            lbl(rv, var, fg=CY, bg=BG_CARD, f=FBOLD).pack(side='left', padx=(0,8))
            lbl(rv, desc, fg=FG_M, bg=BG_CARD).pack(side='left')

        tips2 = section(right, 'TIPS'); tips2.pack(fill='x')
        for tip in ['Multiple lines → random pick each send',
                    '%nick% personaliza por bot',
                    'Style -1 = shout style aleatorio (0-5)']:
            lbl(tips2, f'• {tip}', fg=FG_M, bg=BG_CARD, f=FSMALL,
                justify='left', wraplength=220).pack(anchor='w', padx=8, pady=2)
        return f

    # ─── Accounts page ────────────────────────────────────────────────────────

    def _pg_accounts(self):
        f = frm(self._page_host, bg=BG)
        top = frm(f, bg=BG); top.pack(fill='x', padx=12, pady=8)
        lbl(top, 'ACCOUNT MANAGER', fg=GR, bg=BG, f=FTITLE).pack(side='left')
        r = frm(top, bg=BG); r.pack(side='right')
        btn(r, '✚ Add',        bg='#0a3a18', fg=GR,        cmd=self._show_add_account_dialog).pack(side='left', padx=3)
        btn(r, '🌐 Browser',   bg='#1a3a5c', fg='#7ec8ff', cmd=self._open_login_browser).pack(side='left', padx=3)
        btn(r, '🔍 Health',    bg='#3a1a5c', fg='#cc88ff', cmd=self._health_check_sel).pack(side='left', padx=3)
        btn(r, '📂 Load JSON', bg=BG_BTN,    fg='#fff',    cmd=self._load_accounts_dlg).pack(side='left', padx=3)
        btn(r, '💾 Save JSON', bg=BG_ACT,    fg='#fff',    cmd=self._save_accounts_json).pack(side='left', padx=3)
        btn(r, '▶ All',        bg='#0a3a18', fg=GR,        cmd=self.connect_all).pack(side='left', padx=3)
        btn(r, '■ Disc All',   bg='#3a0a0a', fg=RD,        cmd=self.disconnect_all).pack(side='left', padx=3)
        # Checkbox auto-refresh de sesión expirada
        chk = tk.Checkbutton(r, text='🔄 Auto-refresh', variable=self._auto_refresh_var,
                              bg=BG, fg=FG_M, selectcolor=BG2, activebackground=BG,
                              activeforeground=FG, font=FSMALL, bd=0, highlightthickness=0)
        chk.pack(side='left', padx=(8, 3))

        s = section(f, 'BOTS'); s.pack(fill='both', expand=True, padx=12, pady=(0,4))
        cols = ('#', 'NAME', 'STATUS', 'HOTEL', 'PROXY', 'GROUP')
        self._acc_tree = ttk.Treeview(s, columns=cols, show='headings',
                                       style='Dark.Treeview', selectmode='extended')
        _acc_stretch = {'NAME': True, 'PROXY': True}
        for col, w in zip(cols, [35, 155, 95, 110, 115, 90]):
            self._acc_tree.heading(col, text=col)
            self._acc_tree.column(col, width=w, minwidth=w,
                                  stretch=_acc_stretch.get(col, False), anchor='w')
        for tag, color in TAG_COLORS.items():
            self._acc_tree.tag_configure(tag, foreground=color)
        vsb = tk.Scrollbar(s, orient='vertical', command=self._acc_tree.yview,
                            bg=BG_CARD, troughcolor=BG2, width=7, relief='flat')
        self._acc_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y', pady=6, padx=(0,6))
        self._acc_tree.pack(fill='both', expand=True, padx=8, pady=(4,8))
        self._acc_tree.bind('<<TreeviewSelect>>', self._on_bot_select)
        self._acc_tree.bind('<Double-Button-1>',  self._on_bot_dblclick)
        self._acc_tree.bind('<Button-3>',         lambda e: self._show_ctx_menu(e, self._acc_tree))

        bb = frm(f, bg=BG); bb.pack(fill='x', padx=12, pady=(0,6))
        btn(bb, '▶ Connect Sel.',    bg='#0a3a18', fg=GR,    cmd=self._conn_sel).pack(side='left', padx=(0,4))
        btn(bb, '■ Disconnect Sel.', bg='#3a0a0a', fg=RD,    cmd=self._disc_sel).pack(side='left', padx=(0,4))
        btn(bb, '⊞ Assign Proxy Grp',bg=BG_BTN,   fg='#fff', cmd=self._assign_pg_dialog).pack(side='left', padx=(0,4))
        btn(bb, '📋 View Log',        bg=BG_ACT,   fg='#fff', cmd=self._open_log_window_sel).pack(side='left', padx=(0,4))
        btn(bb, '🗑 Remove Sel.',     bg='#3a0a0a', fg=RD,    cmd=self._remove_sel_accounts).pack(side='right')
        return f

    # ─── Proxies page ────────────────────────────────────────────────────────

    def _pg_proxies(self):
        f = frm(self._page_host, bg=BG)
        top = frm(f, bg=BG); top.pack(fill='x', padx=12, pady=8)
        lbl(top, 'PROXY MANAGER', fg=GR, bg=BG, f=FTITLE).pack(side='left')
        self._prx_cnt = lbl(top, ' | 0 loaded', fg=FG_M, bg=BG, f=FSMALL); self._prx_cnt.pack(side='left')

        body = frm(f, bg=BG); body.pack(fill='both', expand=True, padx=12, pady=(0,8))

        # Left — groups
        left = frm(body, bg=BG, width=220); left.pack(side='left', fill='y', padx=(0,6))
        left.pack_propagate(False)
        gs = section(left, 'PROXY GROUPS'); gs.pack(fill='both', expand=True)
        gr_top = frm(gs, bg=BG_CARD); gr_top.pack(fill='x', padx=8, pady=(8,4))
        self._grp_name_inp = inp(gr_top, w=12); placeholder(self._grp_name_inp, 'Group name')
        self._grp_name_inp.pack(side='left', fill='x', expand=True, padx=(0,4))
        btn(gr_top, '+', bg='#0a3a18', fg=GR, cmd=self._create_pg, padx=6).pack(side='left')
        self._grp_lb = tk.Listbox(gs, bg=BG_INP, fg=FG, selectbackground='#c4dff0',
                                   selectforeground=FG, relief='flat', bd=0, font=FSMALL,
                                   activestyle='none', highlightthickness=0, height=12)
        self._grp_lb.pack(fill='both', expand=True, padx=8, pady=4)
        self._grp_lb.bind('<<ListboxSelect>>', self._on_grp_select)
        btn(gs, '🗑 Delete Group', bg='#3a0a0a', fg=RD,
            cmd=self._delete_pg).pack(fill='x', padx=8, pady=(0,8))

        # Right — global pool + group proxies
        right = frm(body, bg=BG); right.pack(side='left', fill='both', expand=True)

        gps = section(right, 'GLOBAL PROXY POOL'); gps.pack(fill='x', pady=(0,6))
        tb = frm(gps, bg=BG_CARD); tb.pack(fill='x', padx=8, pady=(8,4))
        btn(tb, '📂 Load .txt', bg=BG_BTN, fg='#fff', cmd=self._load_proxies_dlg).pack(side='left', padx=(0,4))
        btn(tb, '💾 Save',      bg=BG_ACT, fg='#fff', cmd=self._save_proxies).pack(side='left', padx=(0,4))
        btn(tb, '🗑 Clear',     bg='#3a0a0a', fg=RD,  cmd=self._clear_proxies).pack(side='left')
        btn(tb, '→ To Group',  bg='#102040', fg=BL,   cmd=self._global_to_grp).pack(side='right')
        lbl(gps, 'ip:port  or  ip:port:user:pass (SOCKS5)', fg=FG_M, bg=BG_CARD, f=FSMALL).pack(anchor='w', padx=8, pady=(0,2))
        self._prx_txt = tk.Text(gps, bg=BG_INP, fg=GR, insertbackground=CY,
                                 font=FMONO, relief='flat', bd=4, highlightthickness=0, height=6)
        self._prx_txt.pack(fill='x', padx=8, pady=(0,8))

        self._grp_sec = section(right, 'GROUP PROXIES — select a group')
        self._grp_sec.pack(fill='both', expand=True)
        grp_tb = frm(self._grp_sec, bg=BG_CARD); grp_tb.pack(fill='x', padx=8, pady=(8,4))
        self._grp_prx_inp = inp(grp_tb, w=24)
        placeholder(self._grp_prx_inp, 'ip:port or ip:port:user:pass')
        self._grp_prx_inp.pack(side='left', fill='x', expand=True, padx=(0,4))
        btn(grp_tb, '+ Add', bg='#0a3a18', fg=GR, cmd=self._add_grp_proxy).pack(side='left')
        self._grp_prx_lb = tk.Listbox(self._grp_sec, bg=BG_INP, fg=GR,
                                       selectbackground='#c4dff0', selectforeground=FG,
                                       relief='flat', bd=0, font=FMONO,
                                       activestyle='none', highlightthickness=0, height=7)
        self._grp_prx_lb.pack(fill='both', expand=True, padx=8, pady=4)
        grp_btm = frm(self._grp_sec, bg=BG_CARD); grp_btm.pack(fill='x', padx=8, pady=(0,8))
        btn(grp_btm, '🗑 Remove',  bg='#3a0a0a', fg=RD,    cmd=self._remove_grp_proxy).pack(side='left', padx=(0,4))
        btn(grp_btm, '📂 Import', bg=BG_BTN,    fg='#fff', cmd=self._import_grp_proxies).pack(side='left', padx=(0,4))
        btn(grp_btm, '💾 Export', bg=BG_ACT,    fg='#fff', cmd=self._export_grp_proxies).pack(side='left')

        self._refresh_grp_lb()
        return f

    # =========================================================================
    # NAVIGATION
    # =========================================================================

    def show_page(self, name: str):
        for pg in self._pages.values(): pg.pack_forget()
        self._pages[name].pack(fill='both', expand=True)
        self._cur_page = name
        if name == 'dashboard':
            self._topbar_dash.pack(fill='x', before=self._page_host)
            self._topbar_ctrl.pack_forget(); self._tabbar.pack_forget()
        elif name == 'control':
            self._topbar_dash.pack_forget()
            self._topbar_ctrl.pack(fill='x', before=self._page_host)
            self._tabbar.pack(fill='x', before=self._page_host)
        else:
            self._topbar_dash.pack_forget()
            self._topbar_ctrl.pack_forget()
            self._tabbar.pack_forget()
        for pid, b in self._nav_btns.items():
            b.config(bg=HABBO_HEADER if pid==name else BG2,
                     fg='#ffffff'    if pid==name else FG_M)

    def show_tab(self, name: str):
        for tf in self._tab_frames.values(): tf.pack_forget()
        if name in self._tab_frames: self._tab_frames[name].pack(fill='both', expand=True)
        self._cur_tab = name
        for tn, b in self._tab_btns.items():
            b.config(bg=HABBO_HEADER if tn==name else '#1d5a72',
                     fg='#ffffff'    if tn==name else FG_M)

    def _get_active_tree(self):
        if self._cur_page == 'dashboard' and hasattr(self, '_dash_tree'): return self._dash_tree
        if self._cur_page == 'accounts'  and hasattr(self, '_acc_tree'):  return self._acc_tree
        return None

    # =========================================================================
    # CONTEXT MENU
    # =========================================================================

    def _show_ctx_menu(self, event, tree):
        row = tree.identify_row(event.y)
        if not row: return
        if row not in tree.selection(): tree.selection_set(row)
        menu = tk.Menu(self.root, tearoff=0, bg=BG_CARD, fg=FG,
                       activebackground=HABBO_HEADER, activeforeground='#fff',
                       relief='flat', bd=1)
        menu.add_command(label='▶  Connect',           command=self._conn_sel)
        menu.add_command(label='■  Disconnect',        command=self._disc_sel)
        menu.add_separator()
        menu.add_command(label='📋 View Full Log',      command=self._open_log_window_sel)
        menu.add_command(label='⊞  Assign Proxy Group', command=self._assign_pg_dialog)
        menu.add_separator()
        menu.add_command(label='♥  Respect',           command=self._act_respect)
        menu.add_command(label='+  Friend Request',    command=self._act_friend)
        menu.add_separator()
        menu.add_command(label='🗑  Remove',            command=self._remove_sel_accounts)
        try: menu.tk_popup(event.x_root, event.y_root)
        finally: menu.grab_release()

    # =========================================================================
    # LOG WINDOW
    # =========================================================================

    def _open_log_window_sel(self):
        tree = self._get_active_tree()
        if not tree: return
        sel = tree.selection()
        if not sel: return
        inst = next((b for b in self.bots if b.index == int(sel[0])), None)
        if inst: self._open_log_window(inst)

    def _open_log_window(self, inst: BotInstance):
        win = tk.Toplevel(self.root)
        win.title(f'Log — Bot #{inst.index}'); win.geometry('700x450'); win.configure(bg=BG)
        hd = tk.Frame(win, bg=HABBO_HEADER); hd.pack(fill='x')
        lbl(hd, f'  📋  Bot #{inst.index} — {inst.get_display_name()}',
            fg='#fff', bg=HABBO_HEADER, f=FHEAD).pack(side='left', padx=8, pady=6)
        txt = tk.Text(win, bg='#111', fg='#c8e0c8', font=FMONO,
                       relief='flat', bd=8, highlightthickness=0, state='disabled')
        txt.tag_config('gr', foreground='#66dd88')
        txt.tag_config('rd', foreground='#ff6666')
        txt.tag_config('cy', foreground='#66ccff')
        txt.tag_config('or', foreground='#ffaa44')
        vsb = tk.Scrollbar(win, orient='vertical', command=txt.yview,
                            bg=BG_CARD, troughcolor='#111', width=8, relief='flat')
        txt.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y'); txt.pack(fill='both', expand=True)

        def populate():
            txt.config(state='normal'); txt.delete('1.0', 'end')
            for line in list(inst.log_buffer):
                tag = ('gr' if any(x in line for x in ('✅','OK','Connected')) else
                       'rd' if any(x in line for x in ('❌','Error','Banned')) else
                       'cy' if any(x in line for x in ('Hotel','Proxy')) else
                       'or' if 'Auto' in line else '')
                txt.insert('end', line + '\n', tag)
            txt.config(state='disabled'); txt.see('end')

        ft = frm(win, bg=BG); ft.pack(fill='x', padx=8, pady=6)
        btn(ft, '⟳ Refresh', bg=BG_BTN,    fg='#fff', cmd=populate,        pady=3).pack(side='left')
        btn(ft, '🗑 Clear',   bg='#3a0a0a', fg=RD,
            cmd=lambda: (inst.log_buffer.clear(), populate()),               pady=3).pack(side='left', padx=4)
        btn(ft, '✖ Close',   bg=BG_CARD,   fg=FG,    cmd=win.destroy,      pady=3).pack(side='right')
        populate()

    def _on_bot_dblclick(self, event):
        tree = self._get_active_tree()
        if not tree: return
        row = tree.identify_row(event.y)
        if not row: return
        inst = next((b for b in self.bots if b.index == int(row)), None)
        if inst: self._open_log_window(inst)

    # =========================================================================
    # PROXY GROUPS
    # =========================================================================

    def _refresh_grp_lb(self):
        self._grp_lb.delete(0, 'end')
        for name in state.proxy_groups:
            self._grp_lb.insert('end', f'{name}  ({len(state.proxy_groups[name].get("proxies",[]))})')
        menu = self._pg_dash_menu['menu']; menu.delete(0, 'end')
        menu.add_command(label='DIRECT', command=lambda: self._sel_pg.set('DIRECT'))
        for name in state.proxy_groups:
            menu.add_command(label=name, command=lambda n=name: self._sel_pg.set(n))

    def _on_grp_select(self, _=None):
        sel = self._grp_lb.curselection()
        if not sel: self._selected_grp = None; return
        self._selected_grp = self._grp_lb.get(sel[0]).split('  ')[0]
        self._refresh_grp_sec()

    def _refresh_grp_sec(self):
        self._grp_prx_lb.delete(0, 'end')
        if self._selected_grp and self._selected_grp in state.proxy_groups:
            for p in state.proxy_groups[self._selected_grp].get('proxies', []):
                self._grp_prx_lb.insert('end', p)

    def _create_pg(self):
        name = self._grp_name_inp.get().strip()
        if not name or name == 'Group name': return
        if name in state.proxy_groups: self._statusbar.err(f'Group "{name}" ya existe'); return
        state.proxy_groups[name] = {'color': '#30728C', 'proxies': [], '_idx': 0}
        self._grp_name_inp.delete(0, 'end')
        self._refresh_grp_lb(); self._statusbar.ok(f'Grupo "{name}" creado')

    def _delete_pg(self):
        if not self._selected_grp: return
        del state.proxy_groups[self._selected_grp]
        self._selected_grp = None
        self._refresh_grp_lb(); self._refresh_grp_sec()

    def _add_grp_proxy(self):
        if not self._selected_grp: self._statusbar.err('Selecciona un grupo'); return
        raw = self._grp_prx_inp.get().strip()
        if not raw or 'ip:port' in raw: return
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        state.proxy_groups[self._selected_grp]['proxies'].extend(lines)
        self._grp_prx_inp.delete(0, 'end')
        self._refresh_grp_lb(); self._refresh_grp_sec()
        self._statusbar.ok(f'Añadidos {len(lines)} proxies')

    def _remove_grp_proxy(self):
        if not self._selected_grp: return
        sel = self._grp_prx_lb.curselection()
        if not sel: return
        proxies = state.proxy_groups[self._selected_grp]['proxies']
        for idx in reversed(sel): del proxies[idx]
        self._refresh_grp_lb(); self._refresh_grp_sec()

    def _import_grp_proxies(self):
        if not self._selected_grp: self._statusbar.err('Selecciona un grupo'); return
        p = filedialog.askopenfilename(filetypes=[('Text','*.txt'),('All','*.*')])
        if not p: return
        try:
            with open(p, 'r') as f: lines = [l.strip() for l in f if l.strip()]
            state.proxy_groups[self._selected_grp]['proxies'].extend(lines)
            self._refresh_grp_lb(); self._refresh_grp_sec()
            self._statusbar.ok(f'Importados {len(lines)} proxies')
        except Exception as e: self._statusbar.err(str(e))

    def _export_grp_proxies(self):
        if not self._selected_grp: return
        p = filedialog.asksaveasfilename(defaultextension='.txt', filetypes=[('Text','*.txt')])
        if not p: return
        lines = state.proxy_groups[self._selected_grp].get('proxies', [])
        try:
            with open(p, 'w') as f: f.write('\n'.join(lines))
            self._statusbar.ok(f'Exportados {len(lines)} proxies')
        except Exception as e: self._statusbar.err(str(e))

    def _global_to_grp(self):
        if not self._selected_grp: self._statusbar.err('Selecciona un grupo'); return
        lines = [l.strip() for l in self._prx_txt.get('1.0','end').splitlines() if l.strip()]
        state.proxy_groups[self._selected_grp]['proxies'].extend(lines)
        self._refresh_grp_lb(); self._refresh_grp_sec()
        self._statusbar.ok(f'Añadidos {len(lines)} proxies globales al grupo')

    def _assign_pg_dialog(self):
        tree = self._get_active_tree()
        if not tree: return
        sel = tree.selection()
        if not sel: self._statusbar.err('Selecciona bots primero'); return
        if not state.proxy_groups: self._statusbar.err('No hay grupos creados'); return

        dlg = tk.Toplevel(self.root)
        dlg.title('Assign Proxy Group'); dlg.configure(bg=CREAM)
        dlg.resizable(False, False); dlg.transient(self.root); dlg.grab_set()
        hd = tk.Frame(dlg, bg=HABBO_HEADER); hd.pack(fill='x')
        lbl(hd, '  ⊞  Assign Proxy Group', fg='#fff', bg=HABBO_HEADER, f=FHEAD).pack(side='left', padx=8, pady=7)
        sep(dlg, '#000').pack(fill='x')
        bd = frm(dlg, bg=CREAM); bd.pack(padx=16, pady=12)
        lbl(bd, f'Asignando a {len(sel)} bot(s):', fg=FG_M, bg=CREAM, f=FSMALL).pack(anchor='w', pady=(0,6))
        pg_var = tk.StringVar(value=list(state.proxy_groups.keys())[0])
        for name in state.proxy_groups:
            count = len(state.proxy_groups[name].get('proxies', []))
            tk.Radiobutton(bd, text=f'{name}  ({count} proxies)', variable=pg_var, value=name,
                           bg=CREAM, fg=FG, selectcolor=BG_INP,
                           activebackground=CREAM, font=FSMALL).pack(anchor='w', pady=2)
        sep(dlg, '#000').pack(fill='x')
        ft = frm(dlg, bg=CREAM); ft.pack(fill='x', padx=14, pady=8)
        btn(ft, 'Cancelar', bg=BG_CARD, fg=FG, cmd=dlg.destroy).pack(side='right', padx=(4,0))
        def do_assign():
            pg = pg_var.get()
            for iid in sel: self._bot_proxy_groups[int(iid)] = pg
            dlg.destroy(); self._statusbar.ok(f'Grupo "{pg}" asignado a {len(sel)} bot(s)')
        btn(ft, '✓ Assign', bg='#0a3a18', fg=GR, cmd=do_assign).pack(side='right')
        dlg.update_idletasks()
        px = self.root.winfo_rootx() + (self.root.winfo_width()  - dlg.winfo_width())  // 2
        py = self.root.winfo_rooty() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f'+{px}+{py}')

    def _assign_pg_to_sel(self):
        pg = self._sel_pg.get()
        tree = self._get_active_tree()
        if not tree: return
        sel = tree.selection()
        if not sel: self._statusbar.err('Selecciona bots primero'); return
        for iid in sel: self._bot_proxy_groups[int(iid)] = pg
        self._statusbar.ok(f'"{pg}" asignado a {len(sel)} bot(s)')

    # =========================================================================
    # CONNECTION
    # =========================================================================

    def _next_proxy_for_bot(self, inst: BotInstance) -> str:
        pg = self._bot_proxy_groups.get(inst.index)
        if pg and pg != 'DIRECT' and pg in state.proxy_groups:
            return state.next_proxy_from_group(pg)
        return state.next_proxy()

    def _get_hotel(self, inst: BotInstance) -> dict:
        if isinstance(inst.account_data, list) and inst.account_data:
            h = inst.account_data[0].get('hotel') if isinstance(inst.account_data[0], dict) else None
            if h: return const.HOTELS.get(h, const.HOTELS['habbo.com'])
        return const.HOTELS.get(self._hotel_var.get(), const.HOTELS['habbo.com'])

    def _connect_bot(self, inst: BotInstance):
        def run():
            try:
                inst.set_status('Preparing')
                proxy = self._next_proxy_for_bot(inst)
                inst.proxy_address = proxy
                hotel = self._get_hotel(inst)
                inst.add_log(f'Hotel: {hotel["name"]} | Proxy: {proxy}')
                sso_proxy = None
                if proxy != 'DIRECT':
                    parts = proxy.split(':')
                    sso_proxy = (f'socks5://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
                                 if len(parts) == 4 else f'socks5://{parts[0]}:{parts[1]}')
                ticket = get_sso_ticket(inst.account_data, sso_proxy, base_url=hotel['base_url'])
                if not ticket:
                    # Comprobar si el fallo es por sesión expirada
                    sess = check_session(inst.account_data, hotel['base_url'], sso_proxy)
                    if sess.get('expired') and self._auto_refresh_var.get():
                        inst.add_log('🔄 Sesión expirada — renovando cookies en navegador...')
                        inst.set_status('Refreshing')
                        refreshed = self._refresh_cookies_browser(inst)
                        if refreshed:
                            ticket = get_sso_ticket(inst.account_data, sso_proxy, base_url=hotel['base_url'])
                    if not ticket:
                        status = 'Expired' if sess.get('expired') else 'Failed'
                        inst.set_status(status)
                        inst.add_log('❌ SSO ticket failed — sesión expirada.' if sess.get('expired')
                                     else '❌ SSO ticket failed.')
                        return
                inst.sso_ticket = ticket; inst.add_log('✅ Ticket OK.'); inst.set_status('Connecting')
                client = HabboClientGUI(
                    sso_ticket=ticket, bot_index=inst.index, proxy=proxy,
                    logger=inst.add_log, status_updater=inst.set_status,
                    mute_updater=inst.set_mute_status,
                    admin_auto_leave_enabled=self._anti_admin.get(),
                    hotel_config=hotel,
                )
                inst.client = client
                inst.set_status('Connected' if client.connect() else 'Failed')
            except Exception as e:
                inst.set_status('Error'); inst.add_log(f'❌ {e}')
        threading.Thread(target=run, daemon=True).start()

    def connect_all(self):
        try: split = int(self._split_n.get())
        except: split = len(self.bots)
        def run():
            count = 0
            for inst in self.bots:
                if inst.status in ('Connected','Connecting','Preparing'): continue
                self._connect_bot(inst); count += 1
                time.sleep(2.0 if count % max(1,split) == 0 else 1.2)
            self.root.after(0, lambda: self._statusbar.ok(f'Connect-all: {count} bots'))
        threading.Thread(target=run, daemon=True).start()

    def disconnect_all(self):
        for inst in self.bots:
            if inst.client: threading.Thread(target=inst.client.disconnect, daemon=True).start()
            inst.set_status('Disconnected')
        self._statusbar.info('Todos los bots desconectados')

    def _conn_sel(self):
        tree = self._get_active_tree()
        if not tree: return
        count = 0
        for iid in tree.selection():
            inst = next((b for b in self.bots if b.index == int(iid)), None)
            if inst and inst.status not in ('Connected','Connecting','Preparing'):
                self._connect_bot(inst); count += 1
        if count: self._statusbar.ok(f'Conectando {count} bot(s)…')

    def _disc_sel(self):
        tree = self._get_active_tree()
        if not tree: return
        count = 0
        for iid in tree.selection():
            inst = next((b for b in self.bots if b.index == int(iid)), None)
            if inst:
                if inst.client: threading.Thread(target=inst.client.disconnect, daemon=True).start()
                inst.set_status('Disconnected'); count += 1
        if count: self._statusbar.info(f'Desconectados {count} bot(s)')

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def _get_clients(self) -> list:
        t = self._target_var.get()
        if t == 'All Connected':
            return [b.client for b in self.bots if b.client and b.client.connected]
        for b in self.bots:
            label = f'Bot #{b.index} — {b.get_display_name().split(" [")[0]}'
            if t == label and b.client and b.client.connected: return [b.client]
        return []

    def _apply(self, fn):
        clients = self._get_clients()
        if not clients:
            habbo_msg(self.root, 'Sin conexión', 'No hay bots conectados en el target.', '⚠'); return
        for c in clients:
            try: fn(c)
            except Exception as e: print(f'Action error: {e}')

    def _act_shout(self):
        m = self._shout_inp.get()
        if m and m != 'Shout msg...': self._apply(lambda c: c.shout(m))

    def _act_say(self):
        m = self._shout_inp.get()
        if m and m != 'Shout msg...': self._apply(lambda c: c.shout(m, 0))

    def _act_whisper(self):
        u = self._wuser_inp.get(); msg = self._wmsg_inp.get()
        if u not in ('','User') and msg not in ('','Msg'):
            self._apply(lambda c: c.whisper(u, msg))

    def _act_motto(self):
        m = self._motto_inp.get()
        if m and m != 'New motto...': self._apply(lambda c: c.change_motto(m))

    def _act_figure(self):
        g = self._gender_var.get(); fig = self._figure_inp.get()
        if fig and 'Figure code' not in fig: self._apply(lambda c: c.update_figure(g, fig))

    def _act_rand_look(self):
        def do(c):
            g = random.choice(['M','F'])
            figs = const.RANDOM_FIGURES_MALE if g=='M' else const.RANDOM_FIGURES_FEMALE
            c.update_figure(g, random.choice(figs))
        self._apply(do)

    def _act_rand_nick(self): self._apply(lambda c: c.change_username(c._generate_meme_nick()))
    def _act_join(self):
        try: rid = int(self._room_var.get())
        except: habbo_msg(self.root,'Error','Room ID inválido.','❌'); return
        self._apply(lambda c: c.join_room(rid))
    def _act_leave(self):      self._apply(lambda c: c.quit_room())
    def _act_stop_all(self):   self._apply(lambda c: c.stop_random_walk())
    def _act_walk(self):
        try: self._apply(lambda c: c.walk(int(self._wx.get()), int(self._wy.get())))
        except: habbo_msg(self.root,'Error','Coordenadas inválidas.','❌')
    def _act_random_walk(self): self._apply(lambda c: (c.set_walk_room_aware(True), c.walk_random(2.5)))
    def _act_stop_walk(self):  self._apply(lambda c: c.stop_random_walk())
    def _act_dance(self):
        try: self._apply(lambda c: c.dance(int(self._dance_var.get())))
        except: pass
    def _act_posture(self, p): self._apply(lambda c: c.change_posture(p))
    def _act_sign(self):
        try: self._apply(lambda c: c.sign(int(self._sign_var.get())))
        except: pass
    def _act_effect(self):
        try: self._apply(lambda c: c.enable_effect(int(self._eff_var.get())))
        except: pass

    def _act_respect(self):
        t = self._tgt_user_inp.get()
        if t and 'Target' not in t:
            def do(c):
                for u in c.users_in_room.values():
                    if u.name.lower()==t.lower() or str(u.web_id)==t:
                        c.respect_user(u.web_id); break
            self._apply(do)

    def _act_friend(self):
        t = self._tgt_user_inp.get()
        if t and 'Target' not in t: self._apply(lambda c: c.request_friend(t))

    def _act_copy_looks(self):
        t = self._tgt_user_inp.get()
        if t and 'Target' not in t: self._apply(lambda c: c.copy_user_looks(t))

    def _act_stalk(self):
        t = self._tgt_user_inp.get()
        if not t or 'Target' in t: return
        def do(c):
            for u in c.users_in_room.values():
                if u.name.lower()==t.lower(): c.walk(u.x, u.y); break
        self._apply(do)

    def _act_nav_fetch(self):
        cat = self._nav_cat.get(); q = self._nav_search.get()
        if 'Search' in q: q = ''
        self._nav_rooms = []; self._nav_lb.delete(0, 'end')
        clients = self._get_clients()
        if clients:
            def cb(rooms):
                self._nav_rooms = rooms; self._nav_lb.delete(0, 'end')
                for r in rooms:
                    self._nav_lb.insert('end', f'{r.user_count:>3}/{r.max_user_count:<3}  {r.room_name}')
            clients[0].navigator_callback = cb
            clients[0].search_navigator(cat, q)

    def _on_nav_dbl(self, _):
        sel = self._nav_lb.curselection()
        if sel and self._nav_rooms and sel[0] < len(self._nav_rooms):
            rid = self._nav_rooms[sel[0]].flat_id
            self._room_var.set(str(rid)); self._act_join()

    def _act_scan(self):
        self._entities_lb.delete(0, 'end')
        cl = self._get_clients()
        if cl:
            for u in cl[0].users_in_room.values():
                self._entities_lb.insert('end', f'{u.name} ({u.gender}) [{u.room_index}]')

    def _toggle_troll(self):
        self._troll_on = not self._troll_on
        self._troll_btn.config(fg=GR if self._troll_on else OR,
                               bg='#0a3a18' if self._troll_on else '#3a1a00')
        if self._troll_on: self._troll_loop()

    def _troll_loop(self):
        if not self._troll_on: return
        m = self._troll_inp.get()
        if m and 'Troll' not in m: self._apply(lambda c: c.shout(m))
        self.root.after(3000, self._troll_loop)

    # ─── Spammer ─────────────────────────────────────────────────────────────

    def _spam_start(self):
        if self._spammer_on: return
        self._spammer_on = True; self._spam_count = 0
        self._spam_status_lbl.config(text='  ● RUNNING', fg=GR)
        threading.Thread(target=self._spam_loop, daemon=True).start()

    def _spam_stop(self):
        self._spammer_on = False
        self._spam_status_lbl.config(text='  ■ STOPPED', fg=RD)

    def _spam_loop(self):
        while self._spammer_on:
            try:
                raw_lines = [l for l in self._spam_msg.get('1.0','end').splitlines() if l.strip()]
                if not raw_lines: time.sleep(1); continue
                delay = float(self._spam_ivl.get())
                style = int(self._spam_style.get())
                for c in self._get_clients():
                    raw = random.choice(raw_lines)
                    room_id = str(getattr(c, 'current_room_id', ''))
                    msg = (raw.replace('%nick%',  c.username)
                              .replace('%index%', str(c.bot_index))
                              .replace('%room%',  room_id)
                              .replace('%count%', str(self._spam_count)))
                    c.shout(msg, style if style >= 0 else random.randint(0, 5))
                self._spam_count += 1
                self.root.after(0, lambda n=self._spam_count:
                                self._spam_cnt_lbl.config(text=f'Sent: {n}'))
                time.sleep(delay)
            except Exception as e: print(f'Spam error: {e}'); time.sleep(1)

    # =========================================================================
    # WEB SERVER
    # =========================================================================

    def _start_web_server(self):
        def run():
            try: _web.run_server(port=WEB_PORT)
            except OSError:
                self.root.after(0, lambda: self._web_lbl.config(
                    text=f'⚠ Puerto {WEB_PORT} ocupado', fg=OR))
            except Exception as e:
                self.root.after(0, lambda: self._web_lbl.config(text=f'WEB error: {e}', fg=RD))
        threading.Thread(target=run, daemon=True).start()
        self.root.after(1500, self._check_web_ready)

    def _check_web_ready(self):
        try:
            import urllib.request
            urllib.request.urlopen(f'http://localhost:{WEB_PORT}/', timeout=2)
            self._web_lbl.config(text=f'● localhost:{WEB_PORT}', fg='#22cc55')
            self._statusbar.ok(f'Web dashboard → localhost:{WEB_PORT}')
        except: self.root.after(1500, self._check_web_ready)

    # =========================================================================
    # HOTEL / HEADERS
    # =========================================================================

    def _on_hotel_change(self, *_):
        h = self._hotel_var.get()
        if h in const.HOTELS: state.hotel = h

    def _fetch_headers_async(self):
        def run():
            result = const.fetch_and_apply_latest_headers(verbose=True)
            if result['error']:
                msg = f'Headers: fallback ({result["error"][:30]})'; color = OR
            else:
                ver = result['version'].replace('WIN63-', '')
                msg = f'✓ {result["protocol"]} {ver[:16]}'; color = '#22cc55'
            self.root.after(0, lambda: self._web_lbl.config(
                text=f'● :{WEB_PORT}  {msg}', fg=color))
        threading.Thread(target=run, daemon=True).start()

    # =========================================================================
    # ADD ACCOUNT
    # =========================================================================

    @staticmethod
    def _parse_cookie_string(raw: str) -> tuple:
        for line in raw.splitlines():
            if line.strip().lower().startswith('cookie:'): raw = line.strip(); break
        if raw.lower().startswith('cookie:'): raw = raw[7:].strip()
        cookies = {}
        for part in raw.split(';'):
            part = part.strip()
            if '=' in part:
                k, _, v = part.partition('='); cookies[k.strip()] = v.strip()
        return cookies.get('session.id',''), cookies.get('browser_token','')

    @staticmethod
    def _build_account_entry(name, hotel, session_id, browser_token):
        entry = []; meta = {}
        if name.strip():  meta['name']  = name.strip()
        if hotel:         meta['hotel'] = hotel
        if meta:          entry.append(meta)
        entry.append({'name': 'session.id',    'value': session_id.strip()})
        entry.append({'name': 'browser_token', 'value': browser_token.strip()})
        return entry

    # =========================================================================
    # MINI BROWSER LOGIN
    # =========================================================================

    def _open_login_browser(self):
        """
        Abre browser_helper.py como subproceso.
        El helper abre un pywebview con el hotel seleccionado, el usuario
        hace login normalmente, y cuando cierra la ventana las cookies se
        leen y se crea el BotInstance automáticamente.
        """
        hotel     = self._hotel_var.get()
        hotel_cfg = const.HOTELS.get(hotel, const.HOTELS['habbo.com'])
        base_url  = hotel_cfg['base_url']

        # Comprobar que pywebview está instalado antes de lanzar
        try:
            import webview as _wv  # noqa
        except ImportError:
            habbo_msg(self.root, 'Módulo faltante',
                      'pywebview no está instalado.\n\n'
                      'Instálalo con:\n  pip install pywebview',
                      '⚠')
            return

        import subprocess, json as _json, sys as _sys

        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'browser_helper.py')
        if not os.path.exists(helper):
            habbo_msg(self.root, 'Error', 'browser_helper.py no encontrado.', '❌')
            return

        self._statusbar.info(f'Abriendo navegador → {hotel} …')

        def _run():
            try:
                proc = subprocess.run(
                    [_sys.executable, helper, base_url, hotel],
                    capture_output=True, text=True, timeout=600
                )
                # La última línea de stdout es el JSON con las cookies
                lines = [l for l in (proc.stdout or '').strip().splitlines() if l.strip()]
                if not lines:
                    self.root.after(0, lambda: self._statusbar.err('El helper no devolvió datos'))
                    return

                data = _json.loads(lines[-1])
                sid  = (data.get('session_id')    or '').strip()
                btk  = (data.get('browser_token') or '').strip()
                err  = data.get('error')

                if err:
                    self.root.after(0, lambda: habbo_msg(
                        self.root, 'Error del navegador', err, '❌'))
                    return

                if sid and btk:
                    entry = self._build_account_entry('', hotel, sid, btk)
                    idx   = max((b.index for b in self.bots), default=0) + 1
                    self.bots.append(BotInstance(entry, idx))
                    self._save_accounts_json()
                    self.root.after(0, lambda: self._statusbar.ok(
                        f'✅ Bot #{idx} añadido desde el navegador ({hotel})'))
                    self.root.after(0, lambda: habbo_msg(
                        self.root, 'Cuenta añadida',
                        f'Bot #{idx} guardado correctamente.\n'
                        f'Hotel: {hotel}\n'
                        f'session.id: {sid[:18]}…\n\n'
                        f'Conéctalo desde Dashboard → ▶ Conn.',
                        '✅'))
                else:
                    self.root.after(0, lambda: self._statusbar.err(
                        'No se detectaron cookies — inicia sesión antes de cerrar'))
                    self.root.after(0, lambda: habbo_msg(
                        self.root, '⚠ Sin cookies',
                        'No se encontraron session.id ni browser_token.\n\n'
                        '• Asegúrate de iniciar sesión completamente\n'
                        '• Cierra la ventana del navegador después del login\n\n'
                        'Alternativa: usa "✚ Add" → pegar Cookie header de DevTools.',
                        '⚠'))

            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: self._statusbar.err('Timeout: navegador cerrado sin login'))
            except _json.JSONDecodeError as e:
                self.root.after(0, lambda: self._statusbar.err(f'JSON inválido del helper: {e}'))
            except Exception as e:
                self.root.after(0, lambda: self._statusbar.err(f'Error navegador: {e}'))

        threading.Thread(target=_run, daemon=True).start()

    # ─── Auto-refresh cookies ─────────────────────────────────────────────────

    def _refresh_cookies_browser(self, inst: 'BotInstance') -> bool:
        """
        Abre browser_helper.py en background para renovar las cookies de `inst`
        cuando la sesión ha expirado.  Bloquea el hilo llamador hasta que el
        usuario completa el login o se agota el tiempo (10 min).

        Retorna True si se obtuvieron cookies nuevas, False en caso contrario.
        """
        import subprocess as _sp, sys as _sys, json as _js

        hotel     = self._get_hotel(inst)
        base_url  = hotel['base_url']
        hotel_name = hotel.get('name', 'habbo.com')

        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'browser_helper.py')
        if not os.path.exists(helper):
            inst.add_log('❌ browser_helper.py no encontrado — renueva las cookies manualmente')
            return False

        self.root.after(0, lambda: self._statusbar.info(
            f'Bot #{inst.index}: abre el navegador y haz login para renovar la sesión'))

        try:
            proc = _sp.run(
                [_sys.executable, helper, base_url, hotel_name],
                capture_output=True, text=True, timeout=600
            )
            lines = [l for l in (proc.stdout or '').strip().splitlines() if l.strip()]
            if not lines:
                inst.add_log('❌ El navegador no devolvió datos')
                return False

            data = _js.loads(lines[-1])
            sid  = (data.get('session_id')    or '').strip()
            btk  = (data.get('browser_token') or '').strip()

            if sid and btk:
                # Actualizar cookies en account_data (in-place)
                for item in (inst.account_data if isinstance(inst.account_data, list) else []):
                    if not isinstance(item, dict): continue
                    if item.get('name') == 'session.id':    item['value'] = sid
                    if item.get('name') == 'browser_token': item['value'] = btk
                self._save_accounts_json()
                inst.add_log(f'✅ Cookies renovadas — session.id: {sid[:14]}…')
                self.root.after(0, lambda: self._statusbar.ok(f'Bot #{inst.index}: sesión renovada'))
                return True
            else:
                inst.add_log('❌ Sin cookies tras renovación — cierra la ventana después del login')
                return False

        except _sp.TimeoutExpired:
            inst.add_log('❌ Timeout: ventana del navegador cerrada sin login')
            return False
        except _js.JSONDecodeError:
            inst.add_log('❌ Respuesta inválida del navegador')
            return False
        except Exception as e:
            inst.add_log(f'❌ Error renovando cookies: {e}')
            return False

    def _save_accounts_json(self) -> bool:
        try:
            data = [b.account_data for b in self.bots]
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), const.ACCOUNTS_FILE)
            with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)
            self._statusbar.ok(f'Guardadas {len(data)} cuentas')
            return True
        except Exception as e:
            habbo_msg(self.root, 'Error', f'No se pudo guardar:\n{e}', '❌'); return False

    # ─── Health check ─────────────────────────────────────────────────────────

    def _health_check_sel(self):
        """
        Verifica las cuentas seleccionadas (o todas si no hay selección) haciendo
        GET /api/user/self con las cookies almacenadas.
        No abre conexión TCP — es una comprobación HTTP rápida.
        """
        tree = self._get_active_tree()
        sel  = tree.selection() if tree else []

        if sel:
            targets = [b for b in self.bots if str(b.index) in sel]
        else:
            targets = list(self.bots)

        if not targets:
            self._statusbar.err('No hay bots para verificar')
            return

        self._statusbar.info(f'Health check: verificando {len(targets)} cuenta(s)…')

        def run():
            ok = expired = err = 0
            for inst in targets:
                hotel  = self._get_hotel(inst)
                # Convertir proxy al formato de requests si es necesario
                proxy  = inst.proxy_address or 'DIRECT'
                sso_p  = None
                if proxy != 'DIRECT':
                    parts = proxy.split(':')
                    sso_p = (f'socks5://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}'
                             if len(parts) == 4 else f'socks5://{parts[0]}:{parts[1]}')

                result = check_session(inst.account_data, hotel['base_url'], sso_p)

                if result['valid']:
                    user = result.get('username') or '?'
                    inst.add_log(f'✅ Sesión válida — usuario: {user}')
                    ok += 1
                elif result['expired']:
                    inst.add_log('❌ Sesión expirada (401/403) — usa 🌐 Browser para renovar')
                    inst.set_status('Expired')
                    expired += 1
                else:
                    inst.add_log('⚠ No se pudo verificar (proxy/red?)')
                    err += 1

            parts_msg = []
            if ok:      parts_msg.append(f'✅ {ok} válida(s)')
            if expired: parts_msg.append(f'❌ {expired} expirada(s)')
            if err:     parts_msg.append(f'⚠ {err} sin respuesta')
            summary = '  |  '.join(parts_msg) if parts_msg else 'Sin resultados'
            self.root.after(0, lambda: self._statusbar.ok(f'Health check: {summary}'))

        threading.Thread(target=run, daemon=True).start()

    def _remove_sel_accounts(self):
        tree = self._get_active_tree()
        if not tree: return
        indices = [int(iid) for iid in tree.selection()]
        if not indices: return
        remove = [b for b in self.bots if b.index in indices]
        for inst in remove:
            if inst.client and inst.client.connected:
                threading.Thread(target=inst.client.disconnect, daemon=True).start()
            self.bots.remove(inst)
        for i, b in enumerate(self.bots): b.index = i + 1
        self._save_accounts_json()
        self._statusbar.ok(f'Eliminadas {len(remove)} cuenta(s)')

    def _show_add_account_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title('Agregar Cuenta'); dlg.configure(bg=CREAM)
        dlg.resizable(False, False); dlg.geometry('520x460')
        dlg.transient(self.root); dlg.grab_set()

        hd = tk.Frame(dlg, bg=HABBO_HEADER); hd.pack(fill='x')
        lbl(hd, '  ➕  AGREGAR CUENTA', fg='#fff', bg=HABBO_HEADER, f=FHEAD).pack(side='left', padx=12, pady=8)
        sep(dlg, '#000').pack(fill='x')
        body = frm(dlg, bg=CREAM); body.pack(fill='both', expand=True, padx=16, pady=10)

        r1 = frm(body, bg=CREAM); r1.pack(fill='x', pady=(0,5))
        lbl(r1, 'Name (optional):', fg=FG_M, bg=CREAM, f=FSMALL, width=16, anchor='e').pack(side='left')
        name_inp = inp(r1, w=26); name_inp.pack(side='left', padx=(6,0))

        r2 = frm(body, bg=CREAM); r2.pack(fill='x', pady=(0,8))
        lbl(r2, 'Hotel:', fg=FG_M, bg=CREAM, f=FSMALL, width=16, anchor='e').pack(side='left')
        hotel_var = tk.StringVar(value=self._hotel_var.get())
        hm = tk.OptionMenu(r2, hotel_var, *const.HOTELS.keys())
        hm.config(bg=BG_BTN, fg='#fff', activebackground=BG_ACT,
                  relief='flat', bd=0, font=FSMALL, width=20, highlightthickness=0)
        hm['menu'].config(bg=BG_BTN, fg='#fff', activebackground=BG_ACT, relief='flat')
        hm.pack(side='left', padx=(6,0))

        sep(body, '#ccc').pack(fill='x', pady=(0,8))
        tab_row = frm(body, bg=CREAM); tab_row.pack(anchor='w', pady=(0,8))
        mode_var = tk.StringVar(value='cookie')
        content  = frm(body, bg=CREAM); content.pack(fill='both', expand=True)
        cookie_f = frm(content, bg=CREAM); manual_f = frm(content, bg=CREAM)

        lbl(cookie_f, 'Pega el header Cookie: de DevTools\n(Network → request → Headers → Cookie)',
            fg=FG_M, bg=CREAM, f=FSMALL, justify='left').pack(anchor='w', pady=(0,4))
        cookie_txt = tk.Text(cookie_f, bg=BG_INP, fg=FG, insertbackground=CY,
                              relief='flat', height=5, font=FMONO, bd=4, highlightthickness=0, wrap='none')
        cookie_txt.pack(fill='x')
        result_row = frm(cookie_f, bg=CREAM); result_row.pack(fill='x', pady=(6,0))
        sid_lbl = lbl(result_row, 'session.id: —', fg=FG_M, bg=CREAM, f=FSMALL); sid_lbl.pack(side='left', padx=(0,12))
        btk_lbl = lbl(result_row, 'browser_token: —', fg=FG_M, bg=CREAM, f=FSMALL); btk_lbl.pack(side='left')
        _parsed = {'sid': '', 'btk': ''}

        def do_parse():
            sid, btk = self._parse_cookie_string(cookie_txt.get('1.0','end').strip())
            _parsed['sid'] = sid; _parsed['btk'] = btk
            sid_lbl.config(text=f'session.id: {"✅" if sid else "❌"}', fg=GR if sid else RD)
            btk_lbl.config(text=f'browser_token: {"✅" if btk else "❌"}', fg=GR if btk else RD)

        btn(cookie_f, '⌕ Parse', bg=BG_BTN, fg='#fff', cmd=do_parse).pack(anchor='e', pady=(6,0))

        lbl(manual_f, 'Introduce los valores directamente:', fg=FG_M, bg=CREAM, f=FSMALL).pack(anchor='w', pady=(0,6))
        r3 = frm(manual_f, bg=CREAM); r3.pack(fill='x', pady=(0,5))
        lbl(r3, 'session.id:', fg=FG_M, bg=CREAM, f=FSMALL, width=14, anchor='e').pack(side='left')
        sid_manual = inp(r3, w=28); sid_manual.pack(side='left', padx=(6,0))
        r4 = frm(manual_f, bg=CREAM); r4.pack(fill='x')
        lbl(r4, 'browser_token:', fg=FG_M, bg=CREAM, f=FSMALL, width=14, anchor='e').pack(side='left')
        btk_manual = inp(r4, w=28); btk_manual.pack(side='left', padx=(6,0))

        def show_mode(m):
            mode_var.set(m)
            (cookie_f if m=='cookie' else manual_f).pack(fill='both', expand=True)
            (manual_f if m=='cookie' else cookie_f).pack_forget()
            tab_c.config(bg=HABBO_HEADER if m=='cookie' else BG_CARD, fg='#fff' if m=='cookie' else FG_M)
            tab_m.config(bg=HABBO_HEADER if m=='manual' else BG_CARD, fg='#fff' if m=='manual' else FG_M)

        tab_c = tk.Button(tab_row, text='Cookie String (recomendado)',
                          bg=HABBO_HEADER, fg='#fff', relief='flat', bd=0,
                          padx=10, pady=4, font=FSMALL, cursor='hand2',
                          command=lambda: show_mode('cookie')); tab_c.pack(side='left')
        tab_m = tk.Button(tab_row, text='Manual', bg=BG_CARD, fg=FG_M,
                          relief='flat', bd=0, padx=10, pady=4, font=FSMALL, cursor='hand2',
                          command=lambda: show_mode('manual')); tab_m.pack(side='left', padx=(4,0))
        cookie_f.pack(fill='both', expand=True)

        sep(body, '#ccc').pack(fill='x', pady=(8,0))
        ft = frm(body, bg=CREAM); ft.pack(fill='x', pady=(8,0))
        btn(ft, 'Cancelar', bg=BG_CARD, fg=FG_M, cmd=dlg.destroy).pack(side='right', padx=(6,0))

        def do_add():
            name  = name_inp.get().strip(); hotel = hotel_var.get()
            if mode_var.get() == 'cookie':
                sid, btk = _parsed['sid'], _parsed['btk']
                if not sid or not btk: habbo_msg(dlg,'Aviso','Parsea las cookies primero.','⚠'); return
            else:
                sid = sid_manual.get().strip(); btk = btk_manual.get().strip()
                if not sid or not btk: habbo_msg(dlg,'Aviso','Rellena session.id y browser_token.','⚠'); return
            entry = self._build_account_entry(name, hotel, sid, btk)
            idx   = max((b.index for b in self.bots), default=0) + 1
            self.bots.append(BotInstance(entry, idx))
            self._save_accounts_json(); dlg.destroy()
            self._statusbar.ok(f'Cuenta #{idx} añadida{" ("+name+")" if name else ""}')

        btn(ft, '✚ Agregar Cuenta', bg='#0a3a18', fg=GR, cmd=do_add).pack(side='right')
        dlg.update_idletasks()
        px = self.root.winfo_rootx() + (self.root.winfo_width()  - dlg.winfo_width())  // 2
        py = self.root.winfo_rooty() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f'+{px}+{py}')

    # =========================================================================
    # LOG PANEL (inline dashboard)
    # =========================================================================

    def _on_bot_select(self, event=None):
        if not hasattr(self, '_dash_log'): return
        tree = self._get_active_tree()
        if not tree: return
        sel = tree.selection()
        if not sel: return
        idx  = int(sel[0])
        inst = next((b for b in self.bots if b.index == idx), None)
        if not inst: return
        self._log_header_lbl.config(
            text=f'  Log — Bot #{idx} {inst.get_display_name()}  [{inst.status}]  Proxy: {inst.proxy_address or "—"}')
        self._dash_log.config(state='normal')
        self._dash_log.delete('1.0', 'end')
        for line in list(inst.log_buffer)[-100:]:
            tag = ('gr' if any(x in line for x in ('✅','OK','Connected')) else
                   'rd' if any(x in line for x in ('❌','Error','Banned')) else
                   'cy' if any(x in line for x in ('Hotel','Proxy')) else
                   'or' if 'Auto' in line else '')
            self._dash_log.insert('end', line + '\n', tag)
        self._dash_log.config(state='disabled')
        self._dash_log.see('end')

    # =========================================================================
    # AUTO-RECONNECT
    # =========================================================================

    def _start_auto_reconnect(self):
   
        def loop():
            while True:
                try: delay = int(self._rec_delay.get())
                except: delay = 30
                time.sleep(max(10, delay))
                if not self._auto_rec.get(): continue
                for inst in list(self.bots):
                    if inst.status in ('Disconnected','Failed','Error'):
                        inst.add_log('\u267b\ufe0f Auto-reconnect...')
                        self._connect_bot(inst); time.sleep(3)
        threading.Thread(target=loop, daemon=True).start()

    # =========================================================================
    # LOAD / SAVE
    # =========================================================================

    def _auto_load(self):
        base = os.path.dirname(os.path.abspath(__file__))
        for path, fn in [(os.path.join(base, const.ACCOUNTS_FILE), self._load_accounts),
                         (os.path.join(base, 'proxies.txt'),       self._load_proxies)]:
            if os.path.exists(path): fn(path)

    def _load_accounts_dlg(self):
        p = filedialog.askopenfilename(filetypes=[('JSON','*.json'),('All','*.*')])
        if p: self._load_accounts(p)

    def _load_accounts(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
            self.bots.clear()
            self.bots.extend(BotInstance(acc, i+1) for i, acc in enumerate(data))
            self._statusbar.ok(f'Cargadas {len(self.bots)} cuentas')
        except Exception as e:
            habbo_msg(self.root, 'Error', f'No se pudo cargar:\n{e}', '\u274c')

    def _load_proxies_dlg(self):
        p = filedialog.askopenfilename(filetypes=[('Texto','*.txt'),('All','*.*')])
        if p: self._load_proxies(p)

    def _load_proxies(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f if l.strip()]
            self.proxies.clear(); self.proxies.extend(lines)
            state.reset_proxy_index()
            self._prx_txt.delete('1.0', 'end')
            self._prx_txt.insert('1.0', '\n'.join(lines))
            self._prx_cnt.config(text=f' | {len(lines)} loaded')
            self._statusbar.ok(f'Cargados {len(lines)} proxies')
        except Exception as e: habbo_msg(self.root, 'Error', str(e), '\u274c')

    def _save_proxies(self):
        lines = [l.strip() for l in self._prx_txt.get('1.0','end').splitlines() if l.strip()]
        self.proxies.clear(); self.proxies.extend(lines)
        state.reset_proxy_index()
        try:
            with open('proxies.txt', 'w') as f: f.write('\n'.join(lines))
            self._prx_cnt.config(text=f' | {len(lines)} loaded')
            self._statusbar.ok(f'Guardados {len(lines)} proxies')
        except Exception as e: habbo_msg(self.root, 'Error', str(e), '\u274c')

    def _clear_proxies(self):
        self.proxies.clear(); self._prx_txt.delete('1.0','end')
        self._prx_cnt.config(text=' | 0 loaded')
        self._statusbar.info('Proxy pool cleared')

    # =========================================================================
    # REFRESH
    # =========================================================================

    def _refresh_targets(self):
        menu = self._target_menu['menu']
        menu.delete(0, 'end')
        menu.add_command(label='All Connected',
                         command=lambda: self._target_var.set('All Connected'))
        for b in self.bots:
            if b.client and b.client.connected:
                label = f'Bot #{b.index} \u2014 {b.get_display_name().split(" [")[0]}'
                menu.add_command(label=label,
                                 command=lambda l=label: self._target_var.set(l))

    def _schedule_refresh(self):
        self._refresh_ui()
        self.root.after(1500, self._schedule_refresh)

    def _refresh_ui(self):
        if not self._ui_ready: return
        filter_text = self._filter_var.get().lower()
        if filter_text in ('filter bots...', ''): filter_text = ''

        connected = sum(1 for b in self.bots if b.status == 'Connected')
        total     = len(self.bots)
        disc      = total - connected

        self._side_stat.config(text=f'{connected}/{total} bots')
        self._statusbar.update_counts(connected, total, len(self.proxies))

        if hasattr(self, '_conn_lbl'):  self._conn_lbl.config(text=f'CONN: {connected}')
        if hasattr(self, '_conn_lbl2'): self._conn_lbl2.config(text=f'CONN: {connected}')
        if hasattr(self, '_disc_lbl'):  self._disc_lbl.config(text=f'DISC: {disc}')
        if hasattr(self, '_disc_lbl2'): self._disc_lbl2.config(text=f'DISC: {disc}')

        self._refresh_targets()

        def _hotel_key(inst):
            if isinstance(inst.account_data, list) and inst.account_data and \
               isinstance(inst.account_data[0], dict):
                return inst.account_data[0].get('hotel', 'habbo.com')
            return 'habbo.com'

        def _tag(inst):
            s = inst.status.lower()
            if s == 'connected':  return 'connected'
            if s == 'expired':    return 'expired'
            if inst.client and getattr(inst.client, 'is_banned', False): return 'banned'
            if s in ('failed','error'): return 'failed'
            if s == 'preparing':  return 'preparing'
            if s == 'connecting': return 'connecting'
            return 'other'

        def _passes(inst):
            if not filter_text: return True
            return (filter_text in inst.get_display_name().lower()
                    or filter_text in inst.status.lower())

        def _prx(inst):
            if inst.proxy_address and inst.proxy_address != 'DIRECT':
                return inst.proxy_address.split(':')[0]
            return '\u2014'

        def _grp(inst): return self._bot_proxy_groups.get(inst.index, '\u2014')

        if hasattr(self, '_dash_tree'):
            sel = set(self._dash_tree.selection())
            self._dash_tree.delete(*self._dash_tree.get_children())
            for b in self.bots:
                if not _passes(b): continue
                self._dash_tree.insert('', 'end', iid=str(b.index), tags=(_tag(b),),
                                       values=(b.index, b.status,
                                               b.get_display_name().split(' [')[0],
                                               _hotel_key(b), _prx(b), _grp(b)))
            for s in sel:
                try: self._dash_tree.selection_add(s)
                except: pass

        if hasattr(self, '_acc_tree'):
            sel = set(self._acc_tree.selection())
            self._acc_tree.delete(*self._acc_tree.get_children())
            for b in self.bots:
                self._acc_tree.insert('', 'end', iid=str(b.index), tags=(_tag(b),),
                                      values=(b.index,
                                              b.get_display_name().split(' [')[0],
                                              b.status, _hotel_key(b), _prx(b), _grp(b)))
            for s in sel:
                try: self._acc_tree.selection_add(s)
                except: pass


# =============================================================================
if __name__ == '__main__':
    root = tk.Tk()
    NetController(root)
    root.mainloop()
