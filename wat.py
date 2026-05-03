import sys
import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
                             QLabel, QSplitter, QFrame, QSpinBox, QFileDialog,
                             QDialog, QTabWidget, QTableWidget, QTableWidgetItem,
                             QTextEdit, QComboBox, QMessageBox, QDialogButtonBox,
                             QHeaderView, QGridLayout, QDoubleSpinBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from io import StringIO
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. UI 質感設定
# ==========================================
LIGHT_BLUE_THEME_QSS = """
QMainWindow, QWidget {
    background-color: #F8FAFC;
    font-family: 'Segoe UI Variable', 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    color: #1E293B;
}
QLabel { color: #1E293B; }
QPushButton {
    background-color: #6366F1; color: #FFFFFF; border: none;
    padding: 8px 18px; border-radius: 8px; font-weight: 600; font-size: 13px;
}
QPushButton:hover { background-color: #4F46E5; }
QPushButton:pressed { background-color: #4338CA; }
QPushButton:disabled { background-color: #C7D2FE; color: #A5B4FC; }
QListWidget {
    background-color: #FFFFFF; color: #1E293B;
    border: 1px solid #E2E8F0; border-radius: 10px;
    padding: 4px; font-size: 13px; outline: none;
}
QListWidget::item {
    padding: 10px 12px; border-radius: 6px; margin: 1px 2px;
}
QListWidget::item:hover { background-color: #F1F5F9; }
QListWidget::item:selected {
    background-color: #EEF2FF; color: #4338CA;
    border-left: 3px solid #6366F1; font-weight: 600; padding-left: 9px;
}
QFrame#DashboardFrame {
    background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px;
}
QSpinBox {
    background-color: #FFFFFF; color: #1E293B;
    border: 1px solid #CBD5E1; border-radius: 8px;
    padding: 5px 8px; font-size: 13px; min-width: 64px;
}
QSpinBox:focus { border-color: #6366F1; }
QSpinBox::up-button, QSpinBox::down-button { width: 16px; }
QPushButton#FilterBtn {
    padding: 5px 16px; font-size: 12px; border-radius: 20px; min-width: 0px;
    border: 1.5px solid #CBD5E1; background-color: #FFFFFF;
    color: #64748B; font-weight: 500;
}
QPushButton#FilterBtn:hover { border-color: #6366F1; color: #6366F1; background-color: #EEF2FF; }
QPushButton#FilterBtn:checked { border-color: #6366F1; background-color: #6366F1; color: #FFFFFF; font-weight: 600; }
QSplitter::handle { background-color: #E2E8F0; width: 1px; }
QScrollBar:vertical { background: #F8FAFC; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #CBD5E1; border-radius: 4px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #94A3B8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { background: #F8FAFC; height: 8px; border-radius: 4px; }
QScrollBar::handle:horizontal { background: #CBD5E1; border-radius: 4px; min-width: 20px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
QTabWidget::pane { border: 1px solid #E2E8F0; border-radius: 8px; background: #FFFFFF; }
QTabBar::tab {
    background: #F1F5F9; color: #64748B; padding: 7px 18px;
    border-radius: 6px; margin-right: 4px; font-weight: 500;
}
QTabBar::tab:selected { background: #6366F1; color: #FFFFFF; font-weight: 600; }
QTabBar::tab:hover:!selected { background: #E2E8F0; color: #1E293B; }
QTableWidget {
    background-color: #FFFFFF; color: #1E293B;
    border: 1px solid #E2E8F0; border-radius: 8px; gridline-color: #F1F5F9;
    font-size: 12px;
}
QTableWidget QHeaderView::section {
    background-color: #F8FAFC; color: #475569;
    border: none; border-bottom: 2px solid #E2E8F0;
    padding: 6px 10px; font-weight: 600; font-size: 12px;
}
QTextEdit {
    background-color: #FFFFFF; color: #1E293B;
    border: 1px solid #CBD5E1; border-radius: 8px; padding: 6px;
    font-size: 12px;
}
QComboBox {
    background-color: #FFFFFF; color: #1E293B;
    border: 1px solid #CBD5E1; border-radius: 8px;
    padding: 5px 10px; font-size: 13px;
}
QComboBox:focus { border-color: #6366F1; }
QComboBox::drop-down { border: none; width: 20px; }
QDialog { background-color: #F8FAFC; }
QMessageBox { background-color: #F8FAFC; }
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

# Param → Tier 預設對應表（可在匯入時覆蓋）
PARAM_TIER_MAP = {
    "N_Vt":   "Tier 1",
    "P_Vt":   "Tier 1",
    "Via_Rc": "Tier 2",
    "Idsat":  "Tier 2",
    "Ioff":   "Tier 3",
    "Igoff":  "Tier 3",
}

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
def gen_batch_data(base_mean, base_std, is_exp=False, n_wafers=25):
    n_sites = 8
    if is_exp:
        lot_mean = base_mean * np.random.uniform(0.9, 1.1)
        w_means = np.random.exponential(lot_mean, (n_wafers, 1))
        sites = w_means + np.random.normal(0, lot_mean * 0.1, (n_wafers, n_sites))
        return np.clip(sites, 1e-6, None)
    else:
        lot_mean = base_mean + np.random.normal(0, base_std * 0.3)
        w_means = np.random.normal(lot_mean, base_std * 0.5, (n_wafers, 1))
        site_bias = np.linspace(-base_std*0.4, base_std*0.4, n_sites)
        sites = np.random.normal(w_means, base_std * 0.2, (n_wafers, n_sites)) + site_bias
        return sites

def generate_mock_data(n_before=50, n_after=50, n_wafers=25):
    np.random.seed(42)
    scenarios = []

    def add_scenario(name, tier, param, base_mean, base_std, target, desc, is_exp=False):
        context_before = [gen_batch_data(base_mean, base_std, is_exp, n_wafers) for _ in range(n_before)]
        context_after  = [gen_batch_data(base_mean, base_std, is_exp, n_wafers) for _ in range(n_after)]

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
    add_scenario("S01_Normal", "Tier 1", "N_Vt", b_mean, b_std, gen_batch_data(b_mean, b_std, n_wafers=n_wafers), "完美常態")
    
    t_02 = gen_batch_data(b_mean, b_std, n_wafers=n_wafers) + 0.05
    add_scenario("S02_P50_High", "Tier 1", "N_Vt", b_mean, b_std, t_02, "整批偏移 +2.5 Sigma")
    
    t_04 = gen_batch_data(b_mean, b_std, n_wafers=n_wafers)
    t_04[min(23, n_wafers-2):, 6:] += 0.08  
    add_scenario("S04_P95_Tail", "Tier 1", "N_Vt", b_mean, b_std, t_04, "尾部2片Wafer局部 Site 飛高")

    t_06 = gen_batch_data(b_mean, b_std * 3, n_wafers=n_wafers)
    add_scenario("S06_Var_Blowup", "Tier 1", "N_Vt", b_mean, b_std, t_06, "P50沒動，但該批散佈(均勻度)變極差")

    r_mean, r_std = 50.0, 1.5
    add_scenario("S08_Normal", "Tier 2", "Via_Rc", r_mean, r_std, gen_batch_data(r_mean, r_std, n_wafers=n_wafers), "阻值常態")

    t_10 = gen_batch_data(r_mean, r_std, n_wafers=n_wafers)
    t_10[n_wafers-1, 3] += 15.0 
    add_scenario("S10_Single_Spike", "Tier 2", "Via_Rc", r_mean, r_std, t_10, "單片單 Site 接觸不良爆表")

    t_11_split = n_wafers // 2
    t_11_a = gen_batch_data(48, 0.5, n_wafers=n_wafers)[:t_11_split]
    t_11_b = gen_batch_data(52, 0.5, n_wafers=n_wafers)[t_11_split:]
    t_11 = np.vstack((t_11_a, t_11_b))
    add_scenario("S11_Bimodal", "Tier 2", "Via_Rc", r_mean, r_std, t_11, "前12片阻值低，後13片阻值高")

    i_mean, i_std = 0.1, 0.1
    add_scenario("S15_Normal", "Tier 3", "Ioff", i_mean, i_std, gen_batch_data(i_mean, i_std, True, n_wafers), "漏電常態", True)

    t_17 = gen_batch_data(i_mean, i_std, True, n_wafers)
    t_17[max(0, n_wafers-5):, :] += 1.5
    add_scenario("S17_Severe_Leak", "Tier 3", "Ioff", i_mean, i_std, t_17, "最後 5 片嚴重漏電", True)

    t_18 = gen_batch_data(i_mean, i_std, True, n_wafers) + 0.4
    add_scenario("S18_Global_Leak", "Tier 3", "Ioff", i_mean, i_std, t_18, "整批漏電值全面變大", True)

    return scenarios


# ==========================================
# 4b. Raw Data 解析器
# ==========================================
def generate_sample_csv_df():
    """產生示範用 DataFrame，格式與 parse_raw_csv() 完全相容，可直接存 CSV 或填入貼上區。
    內容: N_Vt, 5 before + 1 target (偏移 +0.055) + 3 after lots × 10 wafers × 4 sites
    → target 天然呈現 HIGH RISK (Global Shift)。
    """
    rng = np.random.default_rng(seed=42)
    n_wafers, n_sites = 10, 4
    site_cols = [f"Site_{i+1}" for i in range(n_sites)]
    rows = []

    def _add_lots(lot_ids, role, mean, std):
        for lot_id in lot_ids:
            for w in range(n_wafers):
                vals = np.round(rng.normal(mean, std, n_sites), 4)
                rows.append(dict(
                    LotID=lot_id, Role=role, Param="N_Vt",
                    WaferID=f"W{w+1:02d}",
                    **{sc: float(v) for sc, v in zip(site_cols, vals)}
                ))

    _add_lots([f"BL_{i:03d}" for i in range(1, 6)],  "base",   1.000, 0.020)
    _add_lots(["TARGET_001"],                          "target", 1.055, 0.022)
    _add_lots([f"BL_{i:03d}" for i in range(6, 9)],   "base",   1.000, 0.020)
    return pd.DataFrame(rows)


def parse_raw_csv(df, param_tier_overrides=None):
    """將使用者提供的 DataFrame 解析成與 generate_mock_data() 相容的 scenario list。

    必要欄位: LotID, Role (base/before/after/target), Param, Site_1 … Site_N
    選填欄位: WaferID（僅供識別，不影響計算）
    Role 說明: base = before 的別名；base + after 合稱 baseline。
    Tier 由 PARAM_TIER_MAP 自動判定；未知 Param 可透過 param_tier_overrides 指定。
    """
    if param_tier_overrides is None:
        param_tier_overrides = {}

    required_cols = {"LotID", "Role", "Param"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV 缺少必要欄位: {', '.join(sorted(missing))}")

    site_cols = sorted(
        [c for c in df.columns if c.upper().startswith("SITE_")],
        key=lambda x: int(x.split("_")[1]) if len(x.split("_")) > 1 and x.split("_")[1].isdigit() else 0
    )
    if not site_cols:
        raise ValueError("找不到 Site_* 欄位（如 Site_1, Site_2 …）")

    df = df.copy()
    df["Role"]  = df["Role"].str.strip().str.lower()
    df["Role"]  = df["Role"].replace("base", "before")   # base = before 別名
    df["Param"] = df["Param"].str.strip()
    df["LotID"] = df["LotID"].str.strip()

    bad_roles = set(df["Role"].unique()) - {"before", "target", "after"}
    if bad_roles:
        raise ValueError(f"Role 欄有無效值: {bad_roles}（允許 base / before / after / target）")

    def _lots_to_arrays(role_df):
        return [
            lot_df[site_cols].astype(float).values
            for _, lot_df in role_df.groupby("LotID", sort=False)
        ]

    def _split_base_by_target(param_df):
        """依原始列順序，把 base lots 以 target 位置為界分成 before / after。
        多個 target 時，以第一個 target lot 出現的列索引為切割點。
        """
        # 取得 target 第一次出現的列索引
        target_rows = param_df[param_df["Role"] == "target"]
        if target_rows.empty:
            return param_df  # 留給後面的錯誤處理
        first_target_idx = target_rows.index[0]

        def assign_base_role(row):
            if row["Role"] != "base":
                return row["Role"]
            return "before" if row.name < first_target_idx else "after"

        result = param_df.copy()
        result["Role"] = result.apply(assign_base_role, axis=1)
        return result

    scenarios = []
    for param, param_df in df.groupby("Param", sort=False):
        tier = param_tier_overrides.get(param) or PARAM_TIER_MAP.get(param)
        if tier is None:
            raise ValueError(f"Param '{param}' 找不到對應 Tier，請在匯入時指定")
        if tier not in TIER_CONFIG:
            raise ValueError(f"Tier '{tier}' 不合規，必須為 {list(TIER_CONFIG.keys())}")

        # 若有 base role，依時間順序自動分 before/after
        if "base" in param_df["Role"].values:
            param_df = _split_base_by_target(param_df)

        context_before = _lots_to_arrays(param_df[param_df["Role"].isin(["before"])])
        context_after  = _lots_to_arrays(param_df[param_df["Role"] == "after"])
        base_batches   = context_before + context_after
        if len(base_batches) < 2:
            raise ValueError(
                f"Param '{param}' 的 baseline（base/before + after）批次數不足，至少需要 2 批")

        target_df = param_df[param_df["Role"] == "target"]
        if target_df.empty:
            raise ValueError(f"Param '{param}' 沒有 Role=target 的資料")

        for target_lot_id, target_lot_df in target_df.groupby("LotID", sort=False):
            target = target_lot_df[site_cols].astype(float).values
            risk, p50_k, p95_k, p05_k, violated = calculate_k_shift(base_batches, target, tier)

            ctx_lot_meds   = np.array([np.median(b.mean(axis=1)) for b in base_batches])
            target_lot_med = np.median(target.mean(axis=1))
            lot_z = round(
                (target_lot_med - ctx_lot_meds.mean()) / max(ctx_lot_meds.std(ddof=1), 1e-6), 2)

            if abs(lot_z) > LOT_Z_LIMIT:
                violated.append(("LotZ", lot_z, LOT_Z_LIMIT))

            scenarios.append({
                "name":           target_lot_id,
                "risk":           risk,
                "param":          param,
                "desc":           "手動匯入",
                "p50_k":          p50_k,
                "p95_k":          p95_k,
                "p05_k":          p05_k,
                "lot_z":          lot_z,
                "violated":       violated,
                "context_before": context_before,
                "target":         target,
                "context_after":  context_after,
                "base_batches":   base_batches,
            })

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
        ax.set_facecolor('#FAFBFC')
        ax.tick_params(colors='#475569', labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor('#E2E8F0')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_title(title, color='#1E293B', pad=10, weight='bold', fontsize=10)
        ax.set_xlabel(xlabel, color='#64748B', weight='bold', fontsize=9)
        ax.set_ylabel(ylabel, color='#64748B', weight='bold', fontsize=9)
        ax.grid(True, linestyle=':', alpha=0.4, color='#CBD5E1')

# ==========================================
# 4c. Settings 對話框
# ==========================================
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 設定 — K-Shift 門檻")
        self.setFixedWidth(460)
        self._spins = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        note = QLabel(
            "調整各 Tier 的 K-Shift 判定門檻。\n"
            "套用後對後續所有分析立即生效（不影響已計算結果）。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        for col, text in enumerate(["Tier", "P50 門檻", "Tail 門檻 (P95/P05)"]):
            lbl = QLabel(f"<b>{text}</b>")
            lbl.setTextFormat(Qt.TextFormat.RichText)
            grid.addWidget(lbl, 0, col)

        for row_idx, (tier, cfg) in enumerate(TIER_CONFIG.items(), start=1):
            grid.addWidget(QLabel(tier), row_idx, 0)
            spin_p50 = QDoubleSpinBox()
            spin_p50.setRange(0.1, 20.0)
            spin_p50.setSingleStep(0.1)
            spin_p50.setDecimals(1)
            spin_p50.setValue(cfg["P50_LIMIT"])
            grid.addWidget(spin_p50, row_idx, 1)
            spin_tail = QDoubleSpinBox()
            spin_tail.setRange(0.1, 20.0)
            spin_tail.setSingleStep(0.1)
            spin_tail.setDecimals(1)
            spin_tail.setValue(cfg["TAIL_LIMIT"])
            grid.addWidget(spin_tail, row_idx, 2)
            self._spins[tier] = (spin_p50, spin_tail)

        layout.addLayout(grid)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("✅ 套用")
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        btn_box.accepted.connect(self._apply)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _apply(self):
        for tier, (spin_p50, spin_tail) in self._spins.items():
            TIER_CONFIG[tier]["P50_LIMIT"]  = spin_p50.value()
            TIER_CONFIG[tier]["TAIL_LIMIT"] = spin_tail.value()
        self.accept()


# ==========================================
# 4d. 手動匯入對話框
# ==========================================
class RawDataImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("載入自訂 Raw Data")
        self.resize(860, 600)
        self._df = None
        self._scenarios = None
        self._tier_combos = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # ── Tab 1: 從檔案載入 ──────────────────────────────────────
        file_tab = QWidget()
        ft_layout = QVBoxLayout(file_tab)

        browse_row = QHBoxLayout()
        self.lbl_file = QLabel("（未選擇檔案）")
        self.lbl_file.setStyleSheet("color:#6C757D;")
        browse_row.addWidget(self.lbl_file, 1)
        btn_browse = QPushButton("📂 瀏覽…")
        btn_browse.setFixedWidth(110)
        btn_browse.clicked.connect(self._browse_file)
        browse_row.addWidget(btn_browse)
        btn_sample_file = QPushButton("📋 產生範例")
        btn_sample_file.setFixedWidth(110)
        btn_sample_file.clicked.connect(self._save_sample)
        browse_row.addWidget(btn_sample_file)
        ft_layout.addLayout(browse_row)

        self.table_preview = QTableWidget()
        self.table_preview.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.AnyKeyPressed)
        ft_layout.addWidget(self.table_preview)

        update_row = QHBoxLayout()
        update_row.addStretch()
        btn_update = QPushButton("🔄 從表格更新資料")
        btn_update.setFixedWidth(150)
        btn_update.clicked.connect(self._apply_table_edits)
        update_row.addWidget(btn_update)
        ft_layout.addLayout(update_row)
        tabs.addTab(file_tab, "📁 從檔案載入 (.csv / .xlsx)")

        # ── Tab 2: 多檔合併 ────────────────────────────────────────
        multi_tab = QWidget()
        ml_layout = QVBoxLayout(multi_tab)
        ml_top = QHBoxLayout()
        ml_top.addWidget(QLabel("選取多個 CSV/Excel（每檔 = 一個 Param 的所有 Lots）："))
        ml_top.addStretch()
        btn_add_files = QPushButton("➕ 加入檔案")
        btn_add_files.setFixedWidth(110)
        btn_add_files.clicked.connect(self._add_multi_files)
        ml_top.addWidget(btn_add_files)
        btn_clear_files = QPushButton("🗑 清除")
        btn_clear_files.setFixedWidth(80)
        btn_clear_files.clicked.connect(self._clear_multi_files)
        ml_top.addWidget(btn_clear_files)
        ml_layout.addLayout(ml_top)

        # 檔案清單表格：檔名 | 偵測到的 LotID 數 | Param | 指定 Role
        self.multi_table = QTableWidget(0, 4)
        self.multi_table.setHorizontalHeaderLabels(["檔案", "LotID 數", "Param", "Role 覆蓋"])
        self.multi_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.multi_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.multi_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.multi_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.multi_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        ml_layout.addWidget(self.multi_table)

        ml_bottom = QHBoxLayout()
        ml_bottom.addWidget(QLabel("若 CSV 無 Role 欄，統一設為："))
        self.combo_default_role = QComboBox()
        self.combo_default_role.addItems(["base", "target"])
        ml_bottom.addWidget(self.combo_default_role)
        ml_bottom.addStretch()
        btn_merge = QPushButton("🔗 合併並預覽")
        btn_merge.setFixedWidth(130)
        btn_merge.clicked.connect(self._merge_multi_files)
        ml_bottom.addWidget(btn_merge)
        ml_layout.addLayout(ml_bottom)
        self._multi_file_paths = []
        tabs.addTab(multi_tab, "📂 多檔合併")

        # ── Tab 3: 貼上文字 ────────────────────────────────────────
        paste_tab = QWidget()
        pt_layout = QVBoxLayout(paste_tab)
        paste_top_row = QHBoxLayout()
        paste_top_row.addWidget(QLabel("將 CSV 內容貼上（含 header 列）："))
        paste_top_row.addStretch()
        btn_fill = QPushButton("📋 填入範例")
        btn_fill.setFixedWidth(110)
        btn_fill.clicked.connect(self._fill_sample_text)
        paste_top_row.addWidget(btn_fill)
        pt_layout.addLayout(paste_top_row)
        self.txt_paste = QTextEdit()
        self.txt_paste.setPlaceholderText(
            "LotID,Role,Param,WaferID,Site_1,Site_2,...\n"
            "LOT001,base,N_Vt,W01,1.01,1.02,...\n"
            "LOT051,target,N_Vt,W01,1.05,1.06,...\n"
            "（Role: base / before / after / target；WaferID 選填）"
        )
        self.txt_paste.setFont(QFont("Consolas", 10))
        pt_layout.addWidget(self.txt_paste)
        btn_parse = QPushButton("🔍 解析並預覽")
        btn_parse.clicked.connect(self._parse_paste)
        pt_layout.addWidget(btn_parse)
        tabs.addTab(paste_tab, "📋 貼上文字")

        layout.addWidget(tabs)

        # ── 未知 Param → Tier 指派區 ───────────────────────────────
        self.tier_assign_widget = QWidget()
        ta_layout = QVBoxLayout(self.tier_assign_widget)
        ta_layout.setContentsMargins(0, 4, 0, 4)
        ta_layout.addWidget(QLabel("⚙️ 以下 Param 未有預設 Tier，請手動指定："))
        self.tier_assign_grid = QGridLayout()
        ta_layout.addLayout(self.tier_assign_grid)
        self.tier_assign_widget.setVisible(False)
        layout.addWidget(self.tier_assign_widget)

        # ── 狀態列 ─────────────────────────────────────────────────
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # ── OK / Cancel ────────────────────────────────────────────
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("✅ 確認匯入")
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        btn_box.accepted.connect(self._accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ── 內部方法 ───────────────────────────────────────────────────

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 CSV / Excel 檔", "",
            "資料檔 (*.csv *.xlsx);;All Files (*)")
        if not path:
            return
        try:
            df = (pd.read_excel(path, dtype=str)
                  if path.lower().endswith(".xlsx")
                  else pd.read_csv(path, dtype=str))
            self._load_df(df, label=path)
        except Exception as exc:
            self._set_status(f"❌ 讀取失敗：{exc}", ok=False)

    def _parse_paste(self):
        text = self.txt_paste.toPlainText().strip()
        if not text:
            return
        try:
            df = pd.read_csv(StringIO(text), dtype=str)
            self._load_df(df, label="（貼上文字）")
        except Exception as exc:
            self._set_status(f"❌ 解析失敗：{exc}", ok=False)

    def _load_df(self, df, label=""):
        self._df = df
        self.lbl_file.setText(label)
        self._populate_preview(df)
        self._refresh_tier_combos(df)
        self._set_status(f"✅ 已載入 {len(df)} 列 × {len(df.columns)} 欄", ok=True)

    def _populate_preview(self, df):
        max_rows = min(len(df), 500)
        preview = df.iloc[:max_rows]
        self.table_preview.setColumnCount(len(df.columns))
        self.table_preview.setRowCount(len(preview))
        self.table_preview.setHorizontalHeaderLabels(list(df.columns))
        for r, row in enumerate(preview.itertuples(index=False)):
            for c, val in enumerate(row):
                self.table_preview.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))
        self.table_preview.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        if len(df) > max_rows:
            self._set_status(f"⚠️ 資料共 {len(df)} 列，表格僅顯示前 {max_rows} 列供編輯", ok=True)

    def _refresh_tier_combos(self, df):
        while self.tier_assign_grid.count():
            item = self.tier_assign_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._tier_combos.clear()

        if "Param" not in df.columns:
            self.tier_assign_widget.setVisible(False)
            return

        params = df["Param"].str.strip().unique()
        unknown = [p for p in params if p not in PARAM_TIER_MAP]
        if not unknown:
            self.tier_assign_widget.setVisible(False)
            return

        for row_idx, param in enumerate(unknown):
            self.tier_assign_grid.addWidget(QLabel(f"  {param} :"), row_idx, 0)
            combo = QComboBox()
            combo.addItems(list(TIER_CONFIG.keys()))
            self._tier_combos[param] = combo
            self.tier_assign_grid.addWidget(combo, row_idx, 1)
        self.tier_assign_widget.setVisible(True)

    def _set_status(self, msg, ok=True):
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet("color: #198754;" if ok else "color: #DC3545;")

    def _accept(self):
        if self._df is None:
            QMessageBox.warning(self, "尚未載入資料",
                                "請先載入 CSV/Excel 檔案或貼上文字後再確認。")
            return
        overrides = {p: cb.currentText() for p, cb in self._tier_combos.items()}
        try:
            self._scenarios = parse_raw_csv(self._df, overrides)
            self.accept()
        except ValueError as exc:
            QMessageBox.critical(self, "資料格式錯誤", str(exc))

    def get_scenarios(self):
        return self._scenarios or []

    def _save_sample(self):
        """產生範例 CSV → 可選儲存路徑，並載入預覽。"""
        df = generate_sample_csv_df()
        path, _ = QFileDialog.getSaveFileName(
            self, "儲存範例 CSV", "sample_rawdata.csv", "CSV Files (*.csv)")
        if path:
            df.to_csv(path, index=False, encoding="utf-8-sig")
        self._load_df(df, label=path or "（範例資料）")

    def _fill_sample_text(self):
        """將範例 CSV 文字填入貼上區，使用者可直接修改後解析。"""
        df = generate_sample_csv_df()
        self.txt_paste.setPlainText(df.to_csv(index=False))
        self._set_status("已填入範例資料，可修改後按「解析並預覽」", ok=True)

    def _apply_table_edits(self):
        """從表格目前內容重建 DataFrame（套用使用者的儲存格修改）。"""
        if self.table_preview.columnCount() == 0:
            return
        headers = [
            self.table_preview.horizontalHeaderItem(c).text()
            for c in range(self.table_preview.columnCount())
        ]
        rows = []
        for r in range(self.table_preview.rowCount()):
            row = {}
            for c, h in enumerate(headers):
                item = self.table_preview.item(r, c)
                row[h] = item.text() if item else ""
            rows.append(row)
        df = pd.DataFrame(rows)
        self._df = df
        self._refresh_tier_combos(df)
        self._set_status(f"✅ 已套用表格修改，共 {len(df)} 列", ok=True)

    # ── 多檔合併方法 ───────────────────────────────────────────────

    def _add_multi_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "選取 CSV / Excel 檔（可多選）", "",
            "資料檔 (*.csv *.xlsx);;All Files (*)")
        if not paths:
            return
        default_role = self.combo_default_role.currentText()
        for path in paths:
            if path in self._multi_file_paths:
                continue
            try:
                df_tmp = (pd.read_excel(path, dtype=str, nrows=1)
                          if path.lower().endswith(".xlsx")
                          else pd.read_csv(path, dtype=str, nrows=1))
                # 偵測 Param 欄（取第一列非空值）
                param_val = ""
                if "Param" in df_tmp.columns and not df_tmp["Param"].empty:
                    param_val = str(df_tmp["Param"].iloc[0]).strip()
                # 計算 LotID 數（需讀全檔）
                df_full = (pd.read_excel(path, dtype=str)
                           if path.lower().endswith(".xlsx")
                           else pd.read_csv(path, dtype=str))
                if "LotID" in df_full.columns:
                    n_lots = df_full["LotID"].nunique()
                else:
                    n_lots = 1  # 無 LotID 欄 → 整份當一批
                has_role = "Role" in df_full.columns

                row_idx = self.multi_table.rowCount()
                self.multi_table.insertRow(row_idx)
                import os
                self.multi_table.setItem(row_idx, 0, QTableWidgetItem(os.path.basename(path)))
                self.multi_table.setItem(row_idx, 1, QTableWidgetItem(str(n_lots)))
                self.multi_table.setItem(row_idx, 2, QTableWidgetItem(param_val))

                role_combo = QComboBox()
                role_combo.addItems(["（保留檔案內 Role 欄）", "base", "before", "target", "after"])
                if not has_role:
                    idx = role_combo.findText(default_role)
                    if idx >= 0:
                        role_combo.setCurrentIndex(idx)
                self.multi_table.setCellWidget(row_idx, 3, role_combo)
                self._multi_file_paths.append(path)
            except Exception as exc:
                self._set_status(f"❌ 無法讀取 {path}：{exc}", ok=False)

    def _clear_multi_files(self):
        self.multi_table.setRowCount(0)
        self._multi_file_paths.clear()
        self._set_status("已清除所有檔案", ok=True)

    def _merge_multi_files(self):
        if not self._multi_file_paths:
            self._set_status("❌ 尚未加入任何檔案", ok=False)
            return
        dfs = []
        for row_idx, path in enumerate(self._multi_file_paths):
            try:
                df_f = (pd.read_excel(path, dtype=str)
                        if path.lower().endswith(".xlsx")
                        else pd.read_csv(path, dtype=str))

                # 取 Role 覆蓋設定
                role_widget = self.multi_table.cellWidget(row_idx, 3)
                role_override = role_widget.currentText() if role_widget else ""

                # 補 LotID（用檔名去副檔名）
                import os
                fname_stem = os.path.splitext(os.path.basename(path))[0]
                if "LotID" not in df_f.columns:
                    df_f.insert(0, "LotID", fname_stem)

                # 套用 Role 覆蓋（若非「保留」）
                if role_override and role_override != "（保留檔案內 Role 欄）":
                    df_f["Role"] = role_override
                elif "Role" not in df_f.columns:
                    df_f["Role"] = self.combo_default_role.currentText()

                dfs.append(df_f)
            except Exception as exc:
                self._set_status(f"❌ 讀取失敗 {path}：{exc}", ok=False)
                return

        merged = pd.concat(dfs, ignore_index=True)
        self._load_df(merged, label=f"（已合併 {len(self._multi_file_paths)} 個檔案）")


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
        top_bar.addWidget(QLabel("模擬 Wafer 張數:"))
        self.spin_wafers = QSpinBox()
        self.spin_wafers.setRange(5, 200)
        self.spin_wafers.setValue(25)
        top_bar.addWidget(self.spin_wafers)
        top_bar.addSpacing(16)
        self.btn_analyze = QPushButton("🚀 產生模擬資料")
        self.btn_analyze.clicked.connect(self.run_analysis)
        top_bar.addWidget(self.btn_analyze)
        self.btn_export = QPushButton("💾 匯出 CSV")
        self.btn_export.clicked.connect(self.export_csv)
        top_bar.addWidget(self.btn_export)
        self.btn_load_custom = QPushButton("📂 載入自訂資料")
        self.btn_load_custom.clicked.connect(self.load_custom_data)
        top_bar.addWidget(self.btn_load_custom)
        self.btn_settings = QPushButton("⚙️ 設定")
        self.btn_settings.clicked.connect(self.open_settings)
        top_bar.addWidget(self.btn_settings)
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
            "background-color:#FFFFFF; color:#475569; "
            "border:1px solid #E2E8F0; border-left:3px solid #6366F1; "
            "border-radius:8px; padding:6px 14px; font-size:12px;"
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

    def load_custom_data(self):
        dlg = RawDataImportDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_scenarios = dlg.get_scenarios()
            if new_scenarios:
                self.analyzed_data.extend(new_scenarios)
                self.populate_list()

    def open_settings(self):
        SettingsDialog(self).exec()

    def run_analysis(self):
        self.analyzed_data = generate_mock_data(n_wafers=self.spin_wafers.value())
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
        _nw = data['target'].shape[0]
        self.lbl_metrics.setText(
            f"  前 {n_b} 批 ＋ 後 {n_a} 批（共 {n_b+n_a} 批 × {_nw} WM = {(n_b+n_a)*_nw} pts）  |  "
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
        self.canvas.ax_lot.margins(y=0.15)

        # --- 下半部：全歷史 Wafer & Site 散佈圖 (微觀趨勢) ---
        SITE_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
                       '#9467bd', '#8c564b', '#e377c2', '#17becf',
                       '#bcbd22', '#aec7e8', '#ffbb78', '#98df8a']
        n_w = data['target'].shape[0]
        n_s = data['target'].shape[1]
        half_w = max(n_w / 2.0, 1.0)

        for s in range(n_s):
            X_bg = []
            Y_bg = []

            # 處理 Before Batches（每批次用自己的張數計算偏移）
            for b_idx, batch_data in enumerate(data['context_before']):
                b_x = -n_b + b_idx
                bw = batch_data.shape[0]
                bh = max(bw / 2.0, 1.0)
                w_x_offsets = b_x + (np.arange(bw) - bh / 2) / (bh * 1.1 + 1)
                X_bg.extend(w_x_offsets)
                Y_bg.extend(batch_data[:, s])

            # 處理 After Batches（每批次用自己的張數計算偏移）
            for b_idx, batch_data in enumerate(data['context_after']):
                b_x = 1 + b_idx
                bw = batch_data.shape[0]
                bh = max(bw / 2.0, 1.0)
                w_x_offsets = b_x + (np.arange(bw) - bh / 2) / (bh * 1.1 + 1)
                X_bg.extend(w_x_offsets)
                Y_bg.extend(batch_data[:, s])

            sc = SITE_COLORS[s % len(SITE_COLORS)]
            # 1. 畫出背景所有的 Site 點 (低透明度，小點)
            self.canvas.ax_wafer.scatter(X_bg, Y_bg, color=sc, s=6, alpha=0.20, edgecolors='none')

            # 2. 畫出 Target Batch 的 Site 點 (不透明，大點加白邊，並加入圖例)
            target_x = 0 + (np.arange(n_w) - half_w / 2) / (half_w * 1.1 + 1)
            self.canvas.ax_wafer.scatter(target_x, data['target'][:, s],
                                         color=sc, s=40, alpha=0.9,
                                         edgecolor='white', linewidth=0.5, label=f'Site {s+1}')

        self.canvas.ax_wafer.axhline(base_p50, color='#0D6EFD', linestyle='-', linewidth=2, alpha=0.6)
        self.canvas.ax_wafer.axhline(base_p50 + 3*base_std, color='#FD7E14', linestyle='--', alpha=0.6)
        self.canvas.ax_wafer.axhline(base_p50 - 3*base_std, color='#FD7E14', linestyle='--', alpha=0.6)
        
        self.canvas.style_ax(self.canvas.ax_wafer, f"Micro SPC: All Raw Data ({(n_b+n_a+1)*n_w*n_s:,} pts) by Site", f"Batch Timeline ({n_w} Wafers/Lot)", "Site Measurements")
        self.canvas.ax_wafer.set_xlim(-n_b - 2, n_a + 2)
        self.canvas.ax_wafer.margins(y=0.15)
        
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