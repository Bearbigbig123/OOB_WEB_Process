import sys
import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
                             QLabel, QSplitter, QFrame, QSpinBox, QFileDialog)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. UI 質感設定
# ==========================================
LIGHT_BLUE_THEME_QSS = """
QMainWindow { background-color: #F4F7FA; }
QLabel { color: #2C3E50; font-family: 'Segoe UI', Arial; }
QPushButton {
    background-color: #0D6EFD; color: #FFFFFF; border: none;
    padding: 10px 20px; border-radius: 6px; font-weight: bold; font-size: 14px;
}
QPushButton:hover { background-color: #0B5ED7; }
QPushButton:disabled { background-color: #A5C7FE; }
QListWidget {
    background-color: #FFFFFF; color: #495057; border: 1px solid #DEE2E6;
    border-radius: 8px; padding: 5px; font-size: 14px;
}
QListWidget::item { padding: 12px; border-bottom: 1px solid #F1F3F5; }
QListWidget::item:selected {
    background-color: #E7F1FF; color: #0D6EFD; border-left: 4px solid #0D6EFD; font-weight: bold;
}
QFrame#DashboardFrame { background-color: #FFFFFF; border: 1px solid #DEE2E6; border-radius: 8px; }
QSpinBox {
    background-color: #FFFFFF; color: #495057; border: 1px solid #DEE2E6;
    border-radius: 4px; padding: 3px 6px; font-size: 13px; min-width: 58px;
}
QSpinBox::up-button, QSpinBox::down-button { width: 16px; }
QPushButton#FilterBtn {
    padding: 5px 8px; font-size: 12px; border-radius: 4px; min-width: 0px;
    border: 2px solid #DEE2E6; background-color: #F8F9FA; color: #495057; font-weight: normal;
}
QPushButton#FilterBtn:checked { border-color: #0D6EFD; background-color: #E7F1FF; color: #0D6EFD; font-weight: bold; }
"""

# ==========================================
# 2. 核心算法與分級門檻
# ==========================================
TIER_CONFIG = {
    "Tier 1": {"P50_LIMIT": 2.0, "TAIL_LIMIT": 2.8},
    "Tier 2": {"P50_LIMIT": 2.5, "TAIL_LIMIT": 3.2},
    "Tier 3": {"P50_LIMIT": 3.5, "TAIL_LIMIT": 4.5}
}
LOT_Z_LIMIT = 3.0   # 批次層級 Z-Score 警戒門檻

def calculate_k_shift(base_batches, target, tier):
    """base_batches: list of ndarray (25x8); target: ndarray (25x8)
    以 Wafer-Mean 為比較單位，消除 Site-level 相關性帶來的假性樣本膨脹。
    """
    limits = TIER_CONFIG[tier]

    # 每批 25 片 wafer 對 8 Sites 取 mean → 每批 25 個獨立性更高的代表值
    target_wm = target.mean(axis=1)                                        # shape (25,)
    base_wm = np.concatenate([b.mean(axis=1) for b in base_batches])       # shape (2500,)

    base_p  = {p: np.percentile(base_wm,   p) for p in [95, 75, 50, 25, 5]}
    target_p = {p: np.percentile(target_wm, p) for p in [95, 50, 5]}

    sigma_upper  = max((base_p[75] - base_p[50]) / 0.6745, 1e-6)
    sigma_middle = max((base_p[75] - base_p[25]) / 1.349,  1e-6)
    sigma_lower  = max((base_p[50] - base_p[25]) / 0.6745, 1e-6)

    p95_k = (target_p[95] - base_p[95]) / sigma_upper
    p50_k = (target_p[50] - base_p[50]) / sigma_middle
    p05_k = (target_p[5]  - base_p[5])  / sigma_lower

    violated = []
    risk = "PASS"
    if abs(p50_k) > limits["P50_LIMIT"]:
        risk = "HIGH RISK (Global Shift)"
        violated.append(("P50", round(p50_k, 2), limits["P50_LIMIT"]))
    if abs(p95_k) > limits["TAIL_LIMIT"]:
        if risk == "PASS": risk = "POTENTIAL RISK (Tail)"
        violated.append(("P95", round(p95_k, 2), limits["TAIL_LIMIT"]))
    if abs(p05_k) > limits["TAIL_LIMIT"]:
        if risk == "PASS": risk = "POTENTIAL RISK (Tail)"
        violated.append(("P05", round(p05_k, 2), limits["TAIL_LIMIT"]))

    return risk, round(p50_k, 2), round(p95_k, 2), round(p05_k, 2), violated

# ==========================================
# 3. 數據引擎：產出 (25 Wafer x 8 Site)
# ==========================================
def gen_batch_data(base_mean, base_std, is_exp=False):
    if is_exp:
        lot_mean = base_mean * np.random.uniform(0.9, 1.1)
        w_means = np.random.exponential(lot_mean, (25, 1))
        sites = w_means + np.random.normal(0, lot_mean * 0.1, (25, 8))
        return np.clip(sites, 1e-6, None)
    else:
        lot_mean = base_mean + np.random.normal(0, base_std * 0.3)
        w_means = np.random.normal(lot_mean, base_std * 0.5, (25, 1))
        # 模擬 Site 特徵: 例如 Site 1 通常偏低, Site 8 通常偏高 (增加產線真實感)
        site_bias = np.linspace(-base_std*0.4, base_std*0.4, 8) 
        sites = np.random.normal(w_means, base_std * 0.2, (25, 8)) + site_bias
        return sites

def generate_mock_data(n_before=50, n_after=50):
    np.random.seed(42)
    scenarios = []

    def add_scenario(name, tier, param, base_mean, base_std, target, desc, is_exp=False):
        context_before = [gen_batch_data(base_mean, base_std, is_exp) for _ in range(n_before)]
        context_after  = [gen_batch_data(base_mean, base_std, is_exp) for _ in range(n_after)]

        base_batches = context_before + context_after
        risk, p50_k, p95_k, p05_k, violated = calculate_k_shift(base_batches, target, tier)

        # Lot Z-Score：target 這批的 lot-median 偏離 context 分佈幾個標準差
        context_lot_medians = np.array([np.median(b.mean(axis=1)) for b in base_batches])
        target_lot_median   = np.median(target.mean(axis=1))
        lot_z = round((target_lot_median - context_lot_medians.mean()) / max(context_lot_medians.std(ddof=1), 1e-6), 2)

        if abs(lot_z) > LOT_Z_LIMIT:
            violated.append(("LotZ", lot_z, LOT_Z_LIMIT))

        scenarios.append({
            "name": name, "risk": risk, "param": param, "desc": desc,
            "p50_k": p50_k, "p95_k": p95_k, "p05_k": p05_k,
            "lot_z": lot_z, "violated": violated,
            "context_before": context_before,
            "target": target,
            "context_after": context_after,
            "base_batches": base_batches
        })

    b_mean, b_std = 1.0, 0.02
    add_scenario("S01_Normal", "Tier 1", "N_Vt", b_mean, b_std, gen_batch_data(b_mean, b_std), "完美常態")
    
    t_02 = gen_batch_data(b_mean, b_std) + 0.05
    add_scenario("S02_P50_High", "Tier 1", "N_Vt", b_mean, b_std, t_02, "整批偏移 +2.5 Sigma")
    
    t_04 = gen_batch_data(b_mean, b_std)
    t_04[23:, 6:] += 0.08  
    add_scenario("S04_P95_Tail", "Tier 1", "N_Vt", b_mean, b_std, t_04, "尾部2片Wafer局部 Site 飛高")

    t_06 = gen_batch_data(b_mean, b_std * 3)
    add_scenario("S06_Var_Blowup", "Tier 1", "N_Vt", b_mean, b_std, t_06, "P50沒動，但該批散佈(均勻度)變極差")

    r_mean, r_std = 50.0, 1.5
    add_scenario("S08_Normal", "Tier 2", "Via_Rc", r_mean, r_std, gen_batch_data(r_mean, r_std), "阻值常態")

    t_10 = gen_batch_data(r_mean, r_std)
    t_10[24, 3] += 15.0 
    add_scenario("S10_Single_Spike", "Tier 2", "Via_Rc", r_mean, r_std, t_10, "單片單 Site 接觸不良爆表")

    t_11_a = gen_batch_data(48, 0.5)[:12]
    t_11_b = gen_batch_data(52, 0.5)[12:]
    t_11 = np.vstack((t_11_a, t_11_b))
    add_scenario("S11_Bimodal", "Tier 2", "Via_Rc", r_mean, r_std, t_11, "前12片阻值低，後13片阻值高")

    i_mean, i_std = 0.1, 0.1
    add_scenario("S15_Normal", "Tier 3", "Ioff", i_mean, i_std, gen_batch_data(i_mean, i_std, True), "漏電常態", True)

    t_17 = gen_batch_data(i_mean, i_std, True)
    t_17[20:, :] += 1.5
    add_scenario("S17_Severe_Leak", "Tier 3", "Ioff", i_mean, i_std, t_17, "最後 5 片嚴重漏電", True)

    t_18 = gen_batch_data(i_mean, i_std, True) + 0.4
    add_scenario("S18_Global_Leak", "Tier 3", "Ioff", i_mean, i_std, t_18, "整批漏電值全面變大", True)

    return scenarios

# ==========================================
# 4. 圖表渲染元件
# ==========================================
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=8, height=8, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.patch.set_facecolor('#FFFFFF')

        gs = self.fig.add_gridspec(2, 2, width_ratios=[3, 1.1], hspace=0.48, wspace=0.08)
        self.ax_lot   = self.fig.add_subplot(gs[0, :])
        self.ax_wafer = self.fig.add_subplot(gs[1, 0])
        self.ax_dist  = self.fig.add_subplot(gs[1, 1])

        super(MplCanvas, self).__init__(self.fig)

    def style_ax(self, ax, title, xlabel, ylabel):
        ax.set_facecolor('#F8F9FA')
        ax.tick_params(colors='#495057')
        for spine in ax.spines.values():
            spine.set_edgecolor('#DEE2E6')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_title(title, color='#212529', pad=10, weight='bold')
        ax.set_xlabel(xlabel, color='#6C757D', weight='bold')
        ax.set_ylabel(ylabel, color='#6C757D', weight='bold')
        ax.grid(True, linestyle=':', alpha=0.5)

# ==========================================
# 5. 主視窗
# ==========================================
class KShiftDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SPC Full History Site Profiler")
        self.resize(1350, 900)
        self.setStyleSheet(LIGHT_BLUE_THEME_QSS)
        self.analyzed_data = []
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("前批次數:"))
        self.spin_before = QSpinBox()
        self.spin_before.setRange(3, 500)
        self.spin_before.setValue(50)
        top_bar.addWidget(self.spin_before)
        top_bar.addWidget(QLabel("後批次數:"))
        self.spin_after = QSpinBox()
        self.spin_after.setRange(0, 500)
        self.spin_after.setValue(50)
        top_bar.addWidget(self.spin_after)
        top_bar.addSpacing(16)
        self.btn_analyze = QPushButton("🚀 產生產線壓測資料 (自動模擬 Site Pattern)")
        self.btn_analyze.clicked.connect(self.run_analysis)
        top_bar.addWidget(self.btn_analyze)
        self.btn_export = QPushButton("💾 匯出 CSV")
        self.btn_export.clicked.connect(self.export_csv)
        top_bar.addWidget(self.btn_export)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_title = QLabel("📄 批次清單")
        left_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        left_layout.addWidget(left_title)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("篩選:"))
        self.btn_f_high = QPushButton("🔴 HIGH")
        self.btn_f_high.setObjectName("FilterBtn")
        self.btn_f_high.setCheckable(True)
        self.btn_f_high.setChecked(True)
        self.btn_f_high.toggled.connect(self.populate_list)
        filter_row.addWidget(self.btn_f_high)
        self.btn_f_warn = QPushButton("🟡 WARN")
        self.btn_f_warn.setObjectName("FilterBtn")
        self.btn_f_warn.setCheckable(True)
        self.btn_f_warn.setChecked(True)
        self.btn_f_warn.toggled.connect(self.populate_list)
        filter_row.addWidget(self.btn_f_warn)
        self.btn_f_pass = QPushButton("🟢 PASS")
        self.btn_f_pass.setObjectName("FilterBtn")
        self.btn_f_pass.setCheckable(True)
        self.btn_f_pass.setChecked(True)
        self.btn_f_pass.toggled.connect(self.populate_list)
        filter_row.addWidget(self.btn_f_pass)
        left_layout.addLayout(filter_row)

        self.batch_list = QListWidget()
        self.batch_list.itemSelectionChanged.connect(self.update_dashboard)
        left_layout.addWidget(self.batch_list)
        splitter.addWidget(left_widget)

        self.right_frame = QFrame()
        self.right_frame.setObjectName("DashboardFrame")
        right_layout = QVBoxLayout(self.right_frame)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(8)

        self.lbl_title = QLabel("請點擊左側清單")
        self.lbl_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))

        self.lbl_metrics = QLabel("")
        self.lbl_metrics.setFont(QFont("Consolas", 10))
        self.lbl_metrics.setStyleSheet(
            "background-color:#F8F9FA; color:#495057; "
            "border:1px solid #DEE2E6; border-radius:5px; padding:5px 10px;"
        )

        self.lbl_violation = QLabel("")
        self.lbl_violation.setWordWrap(True)
        self.lbl_violation.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_violation.setMinimumHeight(44)

        right_layout.addWidget(self.lbl_title)
        right_layout.addWidget(self.lbl_metrics)
        right_layout.addWidget(self.lbl_violation)

        self.canvas = MplCanvas(self)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)

        splitter.addWidget(self.right_frame)
        splitter.setSizes([350, 1000])
        main_layout.addWidget(splitter)

    def run_analysis(self):
        self.analyzed_data = generate_mock_data(self.spin_before.value(), self.spin_after.value())
        self.populate_list()

    def populate_list(self):
        if not self.analyzed_data:
            return
        self.batch_list.clear()
        show_high = self.btn_f_high.isChecked()
        show_warn = self.btn_f_warn.isChecked()
        show_pass = self.btn_f_pass.isChecked()
        for i, d in enumerate(self.analyzed_data):
            is_high = "HIGH" in d['risk']
            is_warn = "POTENTIAL" in d['risk']
            is_pass = d['risk'] == "PASS"
            if (is_high and show_high) or (is_warn and show_warn) or (is_pass and show_pass):
                icon = "🟢" if is_pass else ("🟡" if is_warn else "🔴")
                wi = QListWidgetItem(f"{icon} [{d['param']}] {d['name']}")
                wi.setData(Qt.ItemDataRole.UserRole, i)
                self.batch_list.addItem(wi)
        if self.batch_list.count() > 0:
            self.batch_list.setCurrentRow(0)

    def export_csv(self):
        if not self.analyzed_data:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出分析結果", "spc_results.csv", "CSV Files (*.csv)")
        if not path:
            return
        rows = []
        for d in self.analyzed_data:
            rows.append({
                "Name":     d['name'],
                "Param":    d['param'],
                "Risk":     d['risk'],
                "P50_K":    d['p50_k'],
                "P95_K":    d['p95_k'],
                "P05_K":    d['p05_k'],
                "Lot_Z":    d['lot_z'],
                "Violated": " | ".join(f"{v[0]}={v[1]}" for v in d['violated']),
            })
        pd.DataFrame(rows).to_csv(path, index=False, encoding='utf-8-sig')

    def update_dashboard(self):
        item = self.batch_list.currentItem()
        if item is None: return
        idx = item.data(Qt.ItemDataRole.UserRole)
        data = self.analyzed_data[idx]
        n_b = len(data['context_before'])
        n_a = len(data['context_after'])

        color = "#198754" if data['risk'] == "PASS" else ("#FD7E14" if "POTENTIAL" in data['risk'] else "#DC3545")
        self.lbl_title.setText(f"Target Batch: {data['name']}")
        self.lbl_title.setStyleSheet(f"color: {color}; font-size: 17px;")
        self.lbl_metrics.setText(
            f"  前 {n_b} 批 ＋ 後 {n_a} 批（共 {n_b+n_a} 批 × 25 WM = {(n_b+n_a)*25} pts）  |  "
            f"K-Shift → P50: {data['p50_k']:+.2f}  P95: {data['p95_k']:+.2f}  P05: {data['p05_k']:+.2f}  |  "
            f"Lot Z: {data['lot_z']:+.2f}"
        )

        # 違規指標醒目 Badge
        if not data['violated']:
            viol_bg   = "#198754"
            viol_html = "✅&nbsp;&nbsp;<b>所有指標正常 — PASS</b>"
        else:
            viol_bg = "#DC3545" if "HIGH" in data['risk'] else "#E8820C"
            icon    = "🚨" if "HIGH" in data['risk'] else "⚠️"
            parts   = []
            for vname, val, limit in data['violated']:
                parts.append(f"<b>{vname}</b>&nbsp;{val:+.2f}&nbsp;<span style='font-weight:normal;font-size:12px;'>(門檻 ±{limit})</span>")
            viol_html = f"{icon}&nbsp;&nbsp;違反指標：{'&nbsp;&nbsp;｜&nbsp;&nbsp;'.join(parts)}"
        self.lbl_violation.setText(
            f'<div style="background-color:{viol_bg}; color:#FFFFFF; padding:10px 16px; '
            f'border-radius:8px; font-size:14px; font-family:Segoe UI,Arial; font-weight:bold;">'
            f'{viol_html}</div>'
        )
        
        self.canvas.ax_lot.clear()
        self.canvas.ax_wafer.clear()
        self.canvas.ax_dist.clear()

        # --- 底色區域（Target = 紅, Baseline = 藍，畫在最底層）---
        for ax in [self.canvas.ax_lot, self.canvas.ax_wafer]:
            ax.axvspan(-0.5, 0.5, alpha=0.13, color='#DC3545', zorder=0)
            ax.axvspan(-n_b - 0.5, -0.5, alpha=0.06, color='#0D6EFD', zorder=0)
            if n_a > 0:
                ax.axvspan(0.5, n_a + 0.5, alpha=0.06, color='#0D6EFD', zorder=0)

        base_wm  = np.concatenate([b.mean(axis=1) for b in data['base_batches']])
        base_p50 = np.percentile(base_wm, 50)
        base_std = (np.percentile(base_wm, 75) - np.percentile(base_wm, 25)) / 1.349

        # --- 上半部：Lot Trend (宏觀趨勢) ---
        x_before = np.arange(-n_b, 0)
        y_before = [np.median(b) for b in data['context_before']]
        x_after = np.arange(1, n_a + 1)
        y_after = [np.median(b) for b in data['context_after']]
        
        self.canvas.ax_lot.plot(x_before, y_before, color='#CED4DA', marker='o', markersize=4, linestyle='-', label='Context Lots')
        self.canvas.ax_lot.plot(x_after, y_after, color='#CED4DA', marker='o', markersize=4, linestyle='-')
        self.canvas.ax_lot.plot([0], [np.median(data['target'])], marker='D', color='#DC3545', markersize=8, label='Target Lot')
        
        self.canvas.ax_lot.axhline(base_p50, color='#0D6EFD', linestyle='-', linewidth=2, label='Baseline P50')
        self.canvas.ax_lot.axhline(base_p50 + 3*base_std, color='#FD7E14', linestyle='--', label='±3 Sigma Limits')
        self.canvas.ax_lot.axhline(base_p50 - 3*base_std, color='#FD7E14', linestyle='--')
        
        self.canvas.style_ax(self.canvas.ax_lot, f"Macro SPC: Lot to Lot Median Trend（前{n_b}後{n_a}批）", "Batch Timeline (0 = Target)", "Lot Median")
        self.canvas.ax_lot.legend(loc='upper right', fontsize=9)
        self.canvas.ax_lot.set_xlim(-n_b - 2, n_a + 2)

        # --- 下半部：全歷史 Wafer & Site 散佈圖 (微觀趨勢) ---
        # 8 種高對比顏色對應 8 個 Site
        SITE_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#17becf']
        
        # 這裡利用 Matplotlib 向量化加速，一次畫出所有批次的特定 Site
        for s in range(8):
            X_bg = []
            Y_bg = []
            
            # 處理 Before Batches
            for b_idx, batch_data in enumerate(data['context_before']):
                b_x = -n_b + b_idx
                # 把 25 片 wafer 在這個 Batch (b_x) 的區間內左右散開 (-0.4 到 +0.4)
                w_x_offsets = b_x + (np.arange(25) - 12) / 28.0 
                X_bg.extend(w_x_offsets)
                Y_bg.extend(batch_data[:, s])
                
            # 處理 After Batches
            for b_idx, batch_data in enumerate(data['context_after']):
                b_x = 1 + b_idx
                w_x_offsets = b_x + (np.arange(25) - 12) / 28.0 
                X_bg.extend(w_x_offsets)
                Y_bg.extend(batch_data[:, s])
                
            # 1. 畫出背景所有的 Site 點 (低透明度，小點)
            self.canvas.ax_wafer.scatter(X_bg, Y_bg, color=SITE_COLORS[s], s=8, alpha=0.25, edgecolors='none')
            
            # 2. 畫出 Target Batch 的 Site 點 (不透明，大點加白邊，並加入圖例)
            target_w_x_offsets = 0 + (np.arange(25) - 12) / 28.0
            self.canvas.ax_wafer.scatter(target_w_x_offsets, data['target'][:, s], 
                                         color=SITE_COLORS[s], s=35, alpha=0.9, 
                                         edgecolor='white', linewidth=0.5, label=f'Site {s+1}')

        self.canvas.ax_wafer.axhline(base_p50, color='#0D6EFD', linestyle='-', linewidth=2, alpha=0.6)
        self.canvas.ax_wafer.axhline(base_p50 + 3*base_std, color='#FD7E14', linestyle='--', alpha=0.6)
        self.canvas.ax_wafer.axhline(base_p50 - 3*base_std, color='#FD7E14', linestyle='--', alpha=0.6)
        
        self.canvas.style_ax(self.canvas.ax_wafer, f"Micro SPC: All Raw Data ({(n_b+n_a+1)*25*8:,} points) colored by Site", "Batch Timeline (25 Wafers per Tick)", "Site Measurements")
        self.canvas.ax_wafer.set_xlim(-n_b - 2, n_a + 2)
        
        # Site 圖例放外面或設定半透明背景，以免遮擋數據
        self.canvas.ax_wafer.legend(loc='upper right', fontsize=8, ncol=4, framealpha=0.9)
        # --- 右下：分佈疊加圖（Baseline WM vs Target WM，水平直方圖對齊散佈圖 y 軸）---
        target_wm_arr = data['target'].mean(axis=1)
        self.canvas.ax_dist.hist(
            base_wm, bins=25, color='#0D6EFD', alpha=0.35,
            density=True, orientation='horizontal', label='Baseline')
        self.canvas.ax_dist.hist(
            target_wm_arr, bins=10, color='#DC3545', alpha=0.55,
            density=True, orientation='horizontal', label='Target')
        self.canvas.ax_dist.axhline(
            base_p50, color='#0D6EFD', linewidth=1.5, linestyle='--')
        self.canvas.ax_dist.axhline(
            float(np.median(target_wm_arr)), color='#DC3545', linewidth=1.5, linestyle='--')
        self.canvas.ax_dist.set_ylim(self.canvas.ax_wafer.get_ylim())
        self.canvas.ax_dist.set_facecolor('#F8F9FA')
        self.canvas.ax_dist.tick_params(colors='#495057', labelsize=7)
        for sp in self.canvas.ax_dist.spines.values():
            sp.set_edgecolor('#DEE2E6')
        self.canvas.ax_dist.spines['top'].set_visible(False)
        self.canvas.ax_dist.spines['right'].set_visible(False)
        self.canvas.ax_dist.set_title(
            "Dist. (WM)", color='#212529', pad=6, weight='bold', fontsize=9)
        self.canvas.ax_dist.set_xlabel(
            "Density", color='#6C757D', weight='bold', fontsize=8)
        self.canvas.ax_dist.yaxis.set_visible(False)
        self.canvas.ax_dist.grid(True, linestyle=':', alpha=0.5)
        self.canvas.ax_dist.legend(fontsize=7, loc='upper right')
        self.canvas.draw()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = KShiftDashboard()
    window.show()
    sys.exit(app.exec())