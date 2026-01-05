import sys
import os
import sqlite3
import math
import statistics
import json
import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, 
    QHeaderView, QTabWidget, QDialog, QFormLayout, QMessageBox, 
    QComboBox, QGroupBox, QScrollArea, QStackedWidget, QFileDialog,
    QFrame, QAbstractItemView, QCheckBox, QDateEdit, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QDate, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIcon, QAction

# PDF Generation
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# ==================== CONFIGURATION ====================
APP_NAME = "Uncertainty Calculator" # Changed from Lab Workbench
ver_str = "0.6"
COPYRIGHT_SIG = f"Eng. Mohammad Telfah copywrite Version {ver_str}"
CONTACT_INFO = """
Developer: Eng. Mohammad Telfah
Phone: +962789841842
Location: Amman - Jordan
"""

# Auth Defaults
DEFAULT_ADMIN_USER = "Admin"
DEFAULT_ADMIN_PASS = "password123"
AUDITOR_USER = "Auditor"
AUDITOR_PASS = "2026"

# ==================== DATABASE MANAGER ====================
class DataManager:
    def __init__(self, db_name="smartlab.db"):
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        c = self.conn.cursor()
        # Parameters
        c.execute("""CREATE TABLE IF NOT EXISTS parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT, unit TEXT, warn_limit REAL, crit_limit REAL
        )""")
        
        # Calibrations
        c.execute("""CREATE TABLE IF NOT EXISTS calibrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            param_id INTEGER, 
            device TEXT, serial TEXT, date TEXT, 
            cert_unc REAL, k_factor REAL, resolution REAL, 
            drift REAL, accuracy REAL, active INTEGER DEFAULT 0
        )""")
        
        # Results
        c.execute("""CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            project TEXT, param TEXT, 
            mean REAL, u_exp REAL, min_trust REAL, max_trust REAL, 
            status TEXT, timestamp TEXT, auditor TEXT,
            device_snap TEXT
        )""")
        
        # Projects (Snapshots)
        c.execute("""CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, 
            name TEXT, 
            last_modified TEXT, 
            data_json TEXT
        )""")

        self.conn.commit()
        self.seed_defaults()

    def seed_defaults(self):
        cur = self.conn.cursor()
        cur.execute("SELECT count(*) FROM parameters")
        if cur.fetchone()[0] == 0:
            defaults = [
                ("H2S","ppb", 10, 20), ("SO2","ppb", 75, 100), ("NO2","ppb", 40, 80),
                ("PM2.5","ug/m3", 35, 50), ("PM10","ug/m3", 150, 200), ("TVOC","ppb", 200, 500),
                ("CO","ppm", 9, 15), ("O3","ppb", 50, 80), 
                ("Temperature","C", 45, 50), ("Humidity","%", 85, 90)
            ]
            for n, u, w, c in defaults:
                self.conn.execute("INSERT INTO parameters (name, unit, warn_limit, crit_limit) VALUES (?,?,?,?)", (n,u,w,c))
            self.conn.commit()

    def query(self, sql, args=(), fetch=False):
        c = self.conn.cursor()
        c.execute(sql, args)
        if fetch: return [dict(row) for row in c.fetchall()]
        self.conn.commit()
        return c.lastrowid

# ==================== CALCULATION ENGINE ====================
class Calculator:
    @staticmethod
    def convert(value, from_u, to_u):
        if value is None: return 0.0
        u1, u2 = str(from_u).lower().strip(), str(to_u).lower().strip()
        if u1 == u2: return value
        
        # Concentration
        if u1 == 'ppm' and u2 == 'ppb': return value * 1000.0
        if u1 == 'ppb' and u2 == 'ppm': return value / 1000.0
        
        # Mass
        if 'mg' in u1 and 'ug' in u2: return value * 1000.0
        if 'ug' in u1 and 'mg' in u2: return value / 1000.0
        
        # Temp
        if u1 == 'c' and u2 == 'k': return value + 273.15
        if u1 == 'k' and u2 == 'c': return value - 273.15
        if u1 == 'c' and u2 == 'f': return (value * 9/5) + 32
        if u1 == 'f' and u2 == 'c': return (value - 32) * 5/9
        
        return value

    @staticmethod
    def calculate(readings, cert_unc, k, res, drift, acc):
        if not readings: return 0, 0
        n = len(readings)
        mean = statistics.mean(readings)
        stdev = statistics.stdev(readings) if n > 1 else 0
        
        u_a = stdev / math.sqrt(n)
        u_cal = cert_unc / (k if k else 2.0)
        u_res = res / math.sqrt(3)
        u_drift = drift / math.sqrt(3)
        u_acc = acc / math.sqrt(3)
        
        u_c = math.sqrt(u_a**2 + u_cal**2 + u_res**2 + u_drift**2 + u_acc**2)
        u_exp = u_c * 2.0
        return mean, u_exp

# ==================== UI STYLES ====================
STYLES = """
    QMainWindow { background-color: #f8fafc; }
    QWidget { font-family: 'Segoe UI', sans-serif; font-size: 13px; color: #334155; }
    
    /* Sidebar */
    QFrame#Sidebar { background-color: #1e293b; color: white; border-right: 1px solid #334155; }
    QLabel#Logo { font-size: 18px; font-weight: bold; color: white; }
    QLabel#Version { background-color: #334155; color: #cbd5e1; padding: 2px 4px; border-radius: 4px; font-size: 10px; }
    QPushButton#NavBtn {
        text-align: left; padding: 10px 15px; border: none; border-radius: 6px;
        color: #94a3b8; background-color: transparent; font-size: 14px;
    }
    QPushButton#NavBtn:hover { background-color: #334155; color: white; }
    QPushButton#NavBtn[checked="true"] { background-color: #0284c7; color: white; }
    
    /* Main Content */
    QTabWidget::pane { border: 1px solid #e2e8f0; background: white; border-radius: 6px; }
    QTabBar::tab { background: transparent; padding: 8px 16px; color: #64748b; font-weight: 500; border-bottom: 2px solid transparent; }
    QTabBar::tab:selected { color: #0284c7; border-bottom: 2px solid #0284c7; }
    
    /* Tables */
    QHeaderView::section { background-color: #f1f5f9; padding: 6px; border: none; font-weight: 600; color: #475569; }
    QTableWidget { border: 1px solid #e2e8f0; gridline-color: #f1f5f9; selection-background-color: #e0f2fe; selection-color: #0f172a; }
    
    /* Buttons */
    QPushButton.primary { background-color: #0284c7; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-weight: 600; }
    QPushButton.primary:hover { background-color: #0369a1; }
    QPushButton.danger { color: #dc2626; background: transparent; border: 1px solid #fee2e2; border-radius: 4px; padding: 4px 8px; }
    QPushButton.danger:hover { background-color: #fef2f2; }
    
    /* Inputs */
    QLineEdit, QComboBox, QDoubleSpinBox, QDateEdit { border: 1px solid #cbd5e1; padding: 4px; border-radius: 4px; }
    QLineEdit:focus { border: 1px solid #0284c7; }
"""

# ==================== CALIBRATION DIALOG ====================
class CalibrationDialog(QDialog):
    def __init__(self, db, param_id, user_role, parent=None):
        super().__init__(parent)
        self.db = db
        self.param_id = param_id
        self.is_auditor = user_role == AUDITOR_USER
        self.setWindowTitle("Manage Calibration Profile")
        self.resize(500, 500)
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        form_grp = QGroupBox("Active Profile")
        form = QFormLayout(form_grp)
        
        self.inp_dev = QLineEdit()
        self.inp_sn = QLineEdit()
        self.inp_date = QDateEdit(); self.inp_date.setDisplayFormat("yyyy-MM-dd"); self.inp_date.setDate(QDate.currentDate())
        self.inp_unc = QDoubleSpinBox(); self.inp_unc.setDecimals(4); self.inp_unc.setMaximum(9999)
        self.inp_k = QDoubleSpinBox(); self.inp_k.setValue(2.0)
        self.inp_res = QDoubleSpinBox(); self.inp_res.setDecimals(4)
        self.inp_drift = QDoubleSpinBox(); self.inp_drift.setDecimals(4)
        self.inp_acc = QDoubleSpinBox(); self.inp_acc.setDecimals(4)

        if self.is_auditor:
            for w in [self.inp_dev, self.inp_sn, self.inp_date, self.inp_unc, self.inp_k, self.inp_res, self.inp_drift, self.inp_acc]:
                w.setReadOnly(True)
                w.setEnabled(False)

        form.addRow("Device Name:", self.inp_dev)
        form.addRow("Serial #:", self.inp_sn)
        form.addRow("Date:", self.inp_date)
        form.addRow("Cert. Unc (U):", self.inp_unc)
        form.addRow("k Factor:", self.inp_k)
        form.addRow("Resolution:", self.inp_res)
        form.addRow("Drift:", self.inp_drift)
        form.addRow("Accuracy:", self.inp_acc)
        layout.addWidget(form_grp)

        if not self.is_auditor:
            btn_save = QPushButton("Save and Set Active")
            btn_save.setProperty("class", "primary")
            btn_save.clicked.connect(self.save)
            layout.addWidget(btn_save)

        # History
        hist_grp = QGroupBox("History")
        hl = QVBoxLayout(hist_grp)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Date", "Device", "Serial", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hl.addWidget(self.table)
        layout.addWidget(hist_grp)

    def load_data(self):
        # Active
        active = self.db.query("SELECT * FROM calibrations WHERE param_id=? AND active=1", (self.param_id,), fetch=True)
        if active:
            r = active[0]
            self.inp_dev.setText(r['device'])
            self.inp_sn.setText(r['serial'])
            self.inp_date.setDate(QDate.fromString(r['date'], "yyyy-MM-dd"))
            self.inp_unc.setValue(r['cert_unc'])
            self.inp_k.setValue(r['k_factor'])
            self.inp_res.setValue(r['resolution'])
            self.inp_drift.setValue(r['drift'])
            self.inp_acc.setValue(r['accuracy'])

        # History
        rows = self.db.query("SELECT * FROM calibrations WHERE param_id=? ORDER BY date DESC", (self.param_id,), fetch=True)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row['date']))
            self.table.setItem(i, 1, QTableWidgetItem(row['device']))
            self.table.setItem(i, 2, QTableWidgetItem(row['serial']))
            status = "Active" if row['active'] else "Inactive"
            self.table.setItem(i, 3, QTableWidgetItem(status))

    def save(self):
        # Deactivate old
        self.db.conn.execute("UPDATE calibrations SET active=0 WHERE param_id=?", (self.param_id,))
        # Insert new
        sql = """INSERT INTO calibrations (param_id, device, serial, date, cert_unc, k_factor, resolution, drift, accuracy, active)
                 VALUES (?,?,?,?,?,?,?,?,?,1)"""
        vals = (
            self.param_id, self.inp_dev.text(), self.inp_sn.text(), self.inp_date.date().toString("yyyy-MM-dd"),
            self.inp_unc.value(), self.inp_k.value(), self.inp_res.value(), self.inp_drift.value(), self.inp_acc.value()
        )
        self.db.conn.execute(sql, vals)
        self.db.conn.commit()
        QMessageBox.information(self, "Saved", "Calibration Profile Updated.")
        self.load_data()

# ==================== LOGIN DIALOG ====================
class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartLab Login")
        self.setFixedSize(300, 180)
        self.user_role = None
        self.username = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        layout.addWidget(QLabel("<h3>Uncertainty Calculator</h3>"))
        
        self.txt_user = QLineEdit(); self.txt_user.setPlaceholderText("Username")
        self.txt_pass = QLineEdit(); self.txt_pass.setPlaceholderText("Password"); self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        
        layout.addWidget(self.txt_user)
        layout.addWidget(self.txt_pass)
        
        btn = QPushButton("Login")
        btn.setProperty("class", "primary")
        btn.clicked.connect(self.auth)
        layout.addWidget(btn)

    def auth(self):
        u = self.txt_user.text().strip()
        p = self.txt_pass.text().strip()
        
        # Hardcoded Auth Logic
        if u == AUDITOR_USER and p == AUDITOR_PASS:
            self.user_role = AUDITOR_USER
            self.username = u
            self.accept()
        elif (u == DEFAULT_ADMIN_USER and p == DEFAULT_ADMIN_PASS) or (u == "Mhmdtelfah" and p == "Jordan@26"):
            self.user_role = "ADMIN"
            self.username = u
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Invalid Credentials")

# ==================== MAIN WINDOW ====================
class MainWindow(QMainWindow):
    def __init__(self, username, role):
        super().__init__()
        self.username = username
        self.role = role
        self.is_auditor = (role == AUDITOR_USER)
        self.db = DataManager()
        
        self.setWindowTitle(f"{APP_NAME} v{ver_str}")
        self.resize(1200, 800)
        self.setup_ui()
        self.refresh_all()

    def setup_ui(self):
        # Container
        container = QWidget()
        self.setCentralWidget(container)
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        # --- Sidebar ---
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sb_layout = QVBoxLayout(sidebar)
        
        # Header
        head = QLabel(f"{APP_NAME}")
        head.setObjectName("Logo")
        ver = QLabel(f"v{ver_str}")
        ver.setObjectName("Version")
        head_lay = QHBoxLayout(); head_lay.addWidget(head); head_lay.addWidget(ver); head_lay.addStretch()
        sb_layout.addLayout(head_lay)
        sb_layout.addWidget(QLabel("ISO 17025 Assistant", objectName="Sub"))
        sb_layout.addSpacing(20)

        # Nav Buttons
        self.stack = QStackedWidget()
        
        nav_grp = QWidget()
        nav_lay = QVBoxLayout(nav_grp); nav_lay.setContentsMargins(0,0,0,0)
        
        btn_wb = QPushButton("Lab Workbench"); btn_wb.setObjectName("NavBtn"); btn_wb.setCheckable(True)
        btn_wb.clicked.connect(lambda: self.switch_view(0, btn_wb))
        btn_wb.setChecked(True); self.current_btn = btn_wb
        
        btn_set = QPushButton("Settings"); btn_set.setObjectName("NavBtn"); btn_set.setCheckable(True)
        btn_set.clicked.connect(lambda: self.switch_view(1, btn_set))
        
        btn_abt = QPushButton("About"); btn_abt.setObjectName("NavBtn"); btn_abt.setCheckable(True)
        btn_abt.clicked.connect(lambda: self.switch_view(2, btn_abt))
        
        nav_lay.addWidget(btn_wb); nav_lay.addWidget(btn_set); nav_lay.addWidget(btn_abt); nav_lay.addStretch()
        sb_layout.addWidget(nav_grp)
        
        # User Profile
        sb_layout.addStretch()
        user_w = QWidget()
        user_l = QHBoxLayout(user_w)
        avatar = QLabel(self.username[0].upper())
        avatar.setStyleSheet("background-color: #0ea5e9; color: white; border-radius: 15px; padding: 5px 10px; font-weight: bold;")
        ul = QVBoxLayout()
        ul.addWidget(QLabel(self.username, styleSheet="color: white; font-weight: bold;"))
        ul.addWidget(QLabel("User" if not self.is_auditor else "Auditor (Read-Only)", styleSheet="color: #94a3b8; font-size: 11px;"))
        user_l.addWidget(avatar); user_l.addLayout(ul)
        sb_layout.addWidget(user_w)

        # --- Main Content ---
        content_area = QWidget()
        ca_layout = QVBoxLayout(content_area)
        ca_layout.addWidget(self.stack)
        
        # Footer Sig
        sig_lbl = QLabel(COPYRIGHT_SIG)
        sig_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        sig_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ca_layout.addWidget(sig_lbl)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(content_area)

        # --- VIEWS ---
        self.init_workbench()
        self.init_settings()
        self.init_about()

    def switch_view(self, idx, btn):
        self.stack.setCurrentIndex(idx)
        if self.current_btn: self.current_btn.setChecked(False)
        btn.setChecked(True)
        self.current_btn = btn

    # ------------------ WORKBENCH VIEW ------------------
    def init_workbench(self):
        wb = QWidget()
        l = QVBoxLayout(wb)
        
        # Header
        top = QHBoxLayout()
        top.addWidget(QLabel("<h2>Workbench</h2>"))
        top.addStretch()
        if self.is_auditor:
            lbl = QLabel("READ ONLY MODE"); lbl.setStyleSheet("background:#fee2e2; color:#b91c1c; padding:4px 8px; border-radius:4px; font-weight:bold;")
            top.addWidget(lbl)
        l.addLayout(top)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self.tab_projects(), "Projects")
        self.tabs.addTab(self.tab_params(), "Parameters")
        self.tabs.addTab(self.tab_measure(), "Measurement Analysis")
        self.tabs.addTab(self.tab_results(), "Results")
        self.tabs.addTab(self.tab_docs(), "Documentation")
        
        l.addWidget(self.tabs)
        self.stack.addWidget(wb)

    def tab_projects(self):
        w = QWidget(); l = QVBoxLayout(w)
        
        top = QHBoxLayout()
        top.addWidget(QLabel("Saved Projects"))
        if not self.is_auditor:
            b = QPushButton("Start New Project")
            b.setProperty("class", "primary")
            b.clicked.connect(self.new_project)
            top.addWidget(b)
        l.addLayout(top)
        
        self.tbl_proj = QTableWidget()
        self.tbl_proj.setColumnCount(3)
        self.tbl_proj.setHorizontalHeaderLabels(["Project Name", "Last Modified", "Actions"])
        self.tbl_proj.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.tbl_proj)
        return w

    def tab_params(self):
        w = QWidget(); l = QVBoxLayout(w)
        
        top = QHBoxLayout()
        top.addWidget(QLabel("Parameter Configuration"))
        if not self.is_auditor:
            b = QPushButton("Add Parameter")
            b.setProperty("class", "primary")
            b.clicked.connect(self.add_param_dialog)
            top.addWidget(b)
        l.addLayout(top)
        
        self.tbl_params = QTableWidget()
        self.tbl_params.setColumnCount(6)
        self.tbl_params.setHorizontalHeaderLabels(["Name", "Unit", "Warn Limit", "Crit Limit", "Cal Status", "Actions"])
        self.tbl_params.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.tbl_params)
        return w

    def tab_measure(self):
        w = QWidget(); l = QVBoxLayout(w)
        
        # Controls
        ctrl = QHBoxLayout()
        self.txt_proj_name = QLineEdit(); self.txt_proj_name.setPlaceholderText("Project Name...")
        if self.is_auditor: self.txt_proj_name.setReadOnly(True)
        
        ctrl.addWidget(QLabel("Project:")); ctrl.addWidget(self.txt_proj_name)
        
        if not self.is_auditor:
            b_save = QPushButton("Save Project"); b_save.clicked.connect(self.save_current_project)
            b_run = QPushButton("Run Analysis"); b_run.setProperty("class", "primary"); b_run.clicked.connect(self.run_analysis)
            ctrl.addWidget(b_save); ctrl.addWidget(b_run)
            
        l.addLayout(ctrl)
        
        # Grid
        self.grid = QTableWidget()
        self.grid.setRowCount(10)
        self.grid.setAlternatingRowColors(True)
        l.addWidget(self.grid)
        return w

    def tab_results(self):
        w = QWidget(); l = QVBoxLayout(w)
        
        top = QHBoxLayout()
        b_pdf = QPushButton("Export PDF Report"); b_pdf.clicked.connect(self.export_pdf)
        top.addStretch(); top.addWidget(b_pdf)
        l.addLayout(top)
        
        self.tbl_res = QTableWidget()
        self.tbl_res.setColumnCount(8)
        self.tbl_res.setHorizontalHeaderLabels(["Project", "Param", "Mean", "U (Exp)", "Min", "Max", "Status", "Date"])
        self.tbl_res.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l.addWidget(self.tbl_res)
        return w
        
    def tab_docs(self):
        w = QWidget(); l = QVBoxLayout(w)
        txt = QLabel("""
        <h3>App Documentation</h3>
        <p><b>Calibration:</b> Use the Parameters tab to manage default calibration profiles.</p>
        <p><b>Analysis:</b> Enter raw data in the Measurement tab. The system handles unit conversions.</p>
        <p><b>Formulas:</b></p>
        <ul>
        <li>u_combined = sqrt(u_a^2 + u_cal^2 + u_res^2 + u_drift^2 + u_acc^2)</li>
        <li>U_expanded = u_combined * 2 (k=2)</li>
        </ul>
        """)
        txt.setWordWrap(True)
        txt.setAlignment(Qt.AlignmentFlag.AlignTop)
        l.addWidget(txt)
        return w

    # ------------------ SETTINGS & ABOUT ------------------
    def init_settings(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("<h2>Settings</h2>"))
        
        prof = QGroupBox("User Profile")
        pf = QFormLayout(prof)
        self.s_user = QLineEdit(self.username)
        self.s_pass = QLineEdit(); self.s_pass.setEchoMode(QLineEdit.EchoMode.Password)
        pf.addRow("Username", self.s_user)
        pf.addRow("New Password", self.s_pass)
        b_upd = QPushButton("Update Profile"); b_upd.clicked.connect(lambda: QMessageBox.information(self, "Info", "Profile updated locally."))
        pf.addRow(b_upd)
        l.addWidget(prof)
        
        data = QGroupBox("Data Management")
        dl = QVBoxLayout(data)
        b_clr = QPushButton("Clear Workspace")
        b_clr.setStyleSheet("color: red; border: 1px solid red; padding: 6px;")
        if self.is_auditor: b_clr.setEnabled(False)
        b_clr.clicked.connect(self.new_project)
        dl.addWidget(b_clr)
        l.addWidget(data)
        l.addStretch()
        self.stack.addWidget(w)

    def init_about(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel(f"<h2>{APP_NAME}</h2>"))
        l.addWidget(QLabel(f"Version {ver_str}"))
        l.addWidget(QLabel("ISO 17025 Uncertainty Assistant"))
        
        cont = QLabel(CONTACT_INFO)
        cont.setStyleSheet("background: white; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0;")
        l.addWidget(cont)
        l.addStretch()
        self.stack.addWidget(w)

    # ------------------ LOGIC ------------------

    def refresh_all(self):
        self.load_params()
        self.load_projects_list()
        self.load_results()
        self.setup_grid_cols()

    def load_params(self):
        params = self.db.query("SELECT * FROM parameters", fetch=True)
        self.tbl_params.setRowCount(len(params))
        for i, p in enumerate(params):
            self.tbl_params.setItem(i, 0, QTableWidgetItem(p['name']))
            self.tbl_params.setItem(i, 1, QTableWidgetItem(p['unit']))
            self.tbl_params.setItem(i, 2, QTableWidgetItem(str(p['warn_limit'])))
            self.tbl_params.setItem(i, 3, QTableWidgetItem(str(p['crit_limit'])))
            
            # Status
            cal = self.db.query("SELECT * FROM calibrations WHERE param_id=? AND active=1", (p['id'],), fetch=True)
            st_txt = "Active" if cal else "Missing"
            st_col = QColor("green") if cal else QColor("orange")
            it_st = QTableWidgetItem(st_txt); it_st.setForeground(st_col)
            self.tbl_params.setItem(i, 4, it_st)
            
            # Btn
            btn = QPushButton("Manage Cal" if not self.is_auditor else "View Cal")
            btn.clicked.connect(lambda ch, pid=p['id']: self.open_cal_dialog(pid))
            self.tbl_params.setCellWidget(i, 5, btn)

    def open_cal_dialog(self, pid):
        d = CalibrationDialog(self.db, pid, self.role, self)
        d.exec()
        self.refresh_all()

    def add_param_dialog(self):
        # Simplistic input dialog logic for brevity
        d = QDialog(self); d.setWindowTitle("Add Param")
        l = QFormLayout(d)
        n = QLineEdit()
        u = QLineEdit()
        w = QDoubleSpinBox(); w.setMaximum(9999)
        c = QDoubleSpinBox(); c.setMaximum(9999)
        l.addRow("Name", n); l.addRow("Unit", u); l.addRow("Warn", w); l.addRow("Crit", c)
        b = QPushButton("Save"); b.clicked.connect(lambda: d.accept())
        l.addRow(b)
        if d.exec():
            if n.text():
                self.db.conn.execute("INSERT INTO parameters (name, unit, warn_limit, crit_limit) VALUES (?,?,?,?)",
                                     (n.text(), u.text(), w.value(), c.value()))
                self.db.conn.commit()
                self.refresh_all()

    def setup_grid_cols(self):
        params = self.db.query("SELECT * FROM parameters", fetch=True)
        self.grid.setColumnCount(len(params))
        self.grid.setHorizontalHeaderLabels([p['name'] for p in params])
        
        # Unit Header (Row 0 workaround or just comboboxes)
        # Using a custom approach: Store params in a list to map columns
        self.grid_params = params
        self.grid_units = []
        
        # We'll use Cell Widgets for unit selection in Row 0? 
        # Better: Just plain inputs. To keep it simple like Angular, we assume input is converted.
        # But let's add a row 0 for "Input Unit"
        if self.grid.rowCount() < 11: self.grid.insertRow(0)
        
        for c, p in enumerate(params):
            cmb = QComboBox()
            opts = [p['unit']]
            if p['unit'] in ['ppm', 'ppb']: opts = ['ppb', 'ppm']
            elif 'm3' in p['unit']: opts = ['ug/m3', 'mg/m3']
            elif p['unit'].lower() in ['c','k','f']: opts = ['C', 'K', 'F']
            cmb.addItems(opts)
            cmb.setCurrentText(p['unit'])
            if self.is_auditor: cmb.setEnabled(False)
            self.grid.setCellWidget(0, c, cmb)

    def run_analysis(self):
        proj = self.txt_proj_name.text() or "Untitled"
        
        for c, p in enumerate(self.grid_params):
            # Get Calibration
            cal_row = self.db.query("SELECT * FROM calibrations WHERE param_id=? AND active=1", (p['id'],), fetch=True)
            if not cal_row: continue # Skip if no cal
            cal = cal_row[0]
            
            # Get Readings
            readings = []
            u_in = self.grid.cellWidget(0, c).currentText()
            
            for r in range(1, self.grid.rowCount()):
                it = self.grid.item(r, c)
                if it and it.text().strip():
                    try:
                        val = float(it.text())
                        val_conv = Calculator.convert(val, u_in, p['unit'])
                        readings.append(val_conv)
                    except: pass
            
            if not readings: continue
            
            # Calc
            mean, u_exp = Calculator.calculate(
                readings, cal['cert_unc'], cal['k_factor'], cal['resolution'], cal['drift'], cal['accuracy']
            )
            
            # Limits
            status = "PASS"
            if p['crit_limit'] and mean > p['crit_limit']: status = "FAIL"
            elif p['warn_limit'] and mean > p['warn_limit']: status = "WARN"
            
            # Save Result
            self.db.conn.execute("""INSERT INTO results (project, param, mean, u_exp, min_trust, max_trust, status, timestamp, auditor, device_snap)
                                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                    (proj, p['name'], mean, u_exp, mean-u_exp, mean+u_exp, status, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), self.username, cal['device']))
        
        self.db.conn.commit()
        QMessageBox.information(self, "Done", "Analysis Complete")
        self.refresh_all()
        self.tabs.setCurrentIndex(3) # Go to results

    def load_results(self):
        res = self.db.query("SELECT * FROM results ORDER BY id DESC", fetch=True)
        self.tbl_res.setRowCount(len(res))
        for i, r in enumerate(res):
            self.tbl_res.setItem(i, 0, QTableWidgetItem(r['project']))
            self.tbl_res.setItem(i, 1, QTableWidgetItem(r['param']))
            self.tbl_res.setItem(i, 2, QTableWidgetItem(f"{r['mean']:.4f}"))
            self.tbl_res.setItem(i, 3, QTableWidgetItem(f"± {r['u_exp']:.4f}"))
            self.tbl_res.setItem(i, 4, QTableWidgetItem(f"{r['min_trust']:.4f}"))
            self.tbl_res.setItem(i, 5, QTableWidgetItem(f"{r['max_trust']:.4f}"))
            
            st = QTableWidgetItem(r['status'])
            if r['status'] == 'FAIL': st.setBackground(QColor("#fee2e2")); st.setForeground(QColor("#b91c1c"))
            elif r['status'] == 'WARN': st.setBackground(QColor("#fef3c7")); st.setForeground(QColor("#b45309"))
            else: st.setBackground(QColor("#dcfce7")); st.setForeground(QColor("#15803d"))
            self.tbl_res.setItem(i, 6, st)
            
            self.tbl_res.setItem(i, 7, QTableWidgetItem(r['timestamp']))

    def load_projects_list(self):
        projs = self.db.query("SELECT * FROM projects", fetch=True)
        self.tbl_proj.setRowCount(len(projs))
        for i, p in enumerate(projs):
            self.tbl_proj.setItem(i, 0, QTableWidgetItem(p['name']))
            self.tbl_proj.setItem(i, 1, QTableWidgetItem(p['last_modified']))
            btn = QPushButton("Load")
            btn.clicked.connect(lambda ch, pid=p['id']: self.load_project_data(pid))
            self.tbl_proj.setCellWidget(i, 2, btn)

    def save_current_project(self):
        # Serialize Grid
        data = {}
        for c in range(self.grid.columnCount()):
            col_vals = {}
            for r in range(1, self.grid.rowCount()):
                it = self.grid.item(r, c)
                if it and it.text(): col_vals[r] = it.text()
            if col_vals: data[c] = col_vals
            
        pid = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        name = self.txt_proj_name.text() or "Untitled"
        js = json.dumps(data)
        
        self.db.conn.execute("INSERT OR REPLACE INTO projects (id, name, last_modified, data_json) VALUES (?,?,?,?)",
                             (pid, name, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), js))
        self.db.conn.commit()
        QMessageBox.information(self, "Saved", "Project saved to history.")
        self.refresh_all()

    def load_project_data(self, pid):
        row = self.db.query("SELECT * FROM projects WHERE id=?", (pid,), fetch=True)
        if not row: return
        p = row[0]
        self.txt_proj_name.setText(p['name'])
        data = json.loads(p['data_json'])
        
        self.grid.clearContents()
        self.setup_grid_cols() # Reset headers
        
        for c_str, rows in data.items():
            c = int(c_str)
            if c < self.grid.columnCount():
                for r_str, val in rows.items():
                    r = int(r_str)
                    self.grid.setItem(r, c, QTableWidgetItem(val))
        
        self.tabs.setCurrentIndex(2) # Go to measure

    def new_project(self):
        self.txt_proj_name.clear()
        self.grid.clearContents()
        self.setup_grid_cols()
        self.tabs.setCurrentIndex(2)

    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Report", "Report.pdf", "PDF Files (*.pdf)")
        if not path: return
        
        doc = SimpleDocTemplate(path, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph(f"{APP_NAME} Report", styles['Title']))
        elements.append(Paragraph(f"Generated by: {self.username} | Date: {datetime.datetime.now()}", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        data = [["Project", "Parameter", "Mean", "Uncertainty", "Status"]]
        res = self.db.query("SELECT * FROM results", fetch=True)
        for r in res:
            data.append([r['project'], r['param'], f"{r['mean']:.3f}", f"{r['u_exp']:.3f}", r['status']])
            
        t = Table(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.navy),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(t)
        
        # Sig
        elements.append(Spacer(1, 40))
        elements.append(Paragraph(COPYRIGHT_SIG, styles['Normal']))
        
        doc.build(elements)
        QMessageBox.information(self, "Success", "PDF Report Generated")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLES)
    
    login = LoginDialog()
    if login.exec() == QDialog.DialogCode.Accepted:
        win = MainWindow(login.username, login.user_role)
        win.show()
        sys.exit(app.exec())