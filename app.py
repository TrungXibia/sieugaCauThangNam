import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from collections import Counter
from io import StringIO

# =============================================================================
# CẤU HÌNH & STYLE
# =============================================================================
st.set_page_config(page_title="Soi Cầu MB - TrungNd@2025", layout="wide")

st.markdown("""
<style>
    .stDataFrame { font-size: 12px; }
    div[data-testid="stExpander"] div[role="button"] p { font-size: 1rem; font-weight: bold; }
    div[data-testid="stExpander"] { margin-bottom: 10px; border: 1px solid #e0e0e0; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

COLORS = ['#ffcccc', '#ccffcc', '#ccccff', '#ffcc99', '#99ccff', '#ff99cc']
CAU_COLOR = '#ffff99'
PREDICT_COLOR = '#ff4b4b'

# =============================================================================
# HÀM XỬ LÝ DỮ LIỆU
# =============================================================================

def safe_int(val, default=0):
    try:
        return int(val)
    except:
        return default

@st.cache_data(ttl=600) 
def fetch_data(type_data='month'):
    try:
        sess = requests.Session()
        if type_data == 'month':
            url = 'https://congcuxoso.com/MienBac/DacBiet/PhoiCauDacBiet/PhoiCauThang5So.aspx'
            r1 = sess.get(url, timeout=10)
            soup = BeautifulSoup(r1.text, 'lxml')
            payload = {inp['name']: inp.get('value', '') for inp in soup.find_all('input', {'type': 'hidden'})}
            m, y = str(datetime.now().month), str(datetime.now().year)
            payload.update({
                'ctl00$ContentPlaceHolder1$ddlThang': m,
                'ctl00$ContentPlaceHolder1$ddlNam': y,
                'ctl00$ContentPlaceHolder1$btnXem': 'Xem'
            })
            r2 = sess.post(url, data=payload, timeout=10)
            table_kw = 'Ngày'
        else: # year
            url = 'https://congcuxoso.com/MienBac/DacBiet/PhoiCauDacBiet/PhoiCauNam5So.aspx'
            r1 = sess.get(url, timeout=10)
            soup = BeautifulSoup(r1.text, 'lxml')
            payload = {inp['name']: inp.get('value', '') for inp in soup.find_all('input', {'type': 'hidden'})}
            y = str(datetime.now().year)
            payload.update({
                'ctl00$ContentPlaceHolder1$ddlNam': y,
                'ctl00$ContentPlaceHolder1$btnXem': 'Xem'
            })
            r2 = sess.post(url, data=payload, timeout=10)
            table_kw = 'TH1'

        soup2 = BeautifulSoup(r2.text, 'lxml')
        table = next(t for t in soup2.find_all('table') if t.find('tr') and table_kw in t.find('tr').get_text())
        df = pd.read_html(StringIO(str(table)), header=0)[0].fillna('')
        
        def fmt(v, col_name):
            s = str(v).strip()
            if not s or s == '-----': return ''
            if s.endswith('.0'): s = s[:-2]
            if col_name == 'Ngày': return s
            return s.zfill(5)
        
        df = df.apply(lambda col: col.map(lambda v: fmt(v, col.name)))
        return df
    except Exception as e:
        st.error(f"Lỗi lấy dữ liệu: {e}")
        return None

# --- HÀM SO KHỚP (ĐÃ CẬP NHẬT QUY TẮC KÉP) ---
def matches_last_two_digits(value, pattern, exact=False):
    """
    value: Giá trị ô (ví dụ '12345')
    pattern: Mẫu (ví dụ '53' hoặc '00')
    exact: True (Chính xác 2 số cuối), False (Có chứa)
    """
    val_str = str(value).strip()
    if not val_str or not pattern:
        return False

    if exact:
        # Chế độ chính xác: Phải cắt lấy 2 số cuối để so sánh
        if len(val_str) < 2: return False
        return val_str[-2:] == pattern
    else:
        # Chế độ "Có chứa" (Toàn bộ chuỗi)
        
        # 1. Xử lý trường hợp KÉP (00, 11, ..., 99)
        # Quy tắc: 00 chỉ cần có 1 số 0; 11 chỉ cần có 1 số 1...
        if pattern[0] == pattern[1]:
            return pattern[0] in val_str
            
        # 2. Xử lý trường hợp THƯỜNG (01, 23...)
        # Quy tắc: Phải chứa đủ cả 2 ký tự
        temp_val = val_str
        for char in pattern:
            if char in temp_val:
                # Tìm thấy thì xóa ký tự đó đi để kiểm tra tiếp ký tự thứ 2
                temp_val = temp_val.replace(char, "", 1)
            else:
                return False
        return True

def get_prev_cell_year(df, row_idx, col_name):
    if row_idx > 0:
        return row_idx - 1, col_name
    
    if not col_name.startswith("TH"): return -1, None
    m = int(col_name[2:])
    pm = 12 if m == 1 else m - 1
    pcol = f"TH{pm}"
    
    if pcol not in df.columns: return -1, None
    col_data = df[pcol]
    for r in range(len(col_data)-1, -1, -1):
        if col_data.iloc[r] != '':
            return r, pcol
    return -1, pcol

# =============================================================================
# LOGIC TÌM CẦU
# =============================================================================

def get_patterns(df, is_year_data, row_idx, col_name, num_patterns):
    patterns = []
    pattern_months = set()
    
    if is_year_data:
        cur_day, cur_col = row_idx, col_name
        for _ in range(num_patterns):
            p_day, p_col = get_prev_cell_year(df, cur_day, cur_col)
            if p_day < 0 or not p_col:
                patterns.append('')
            else:
                val = df.iloc[p_day][p_col]
                patterns.append(val[-2:] if len(val) >= 2 else '')
                pattern_months.add(p_col)
                cur_day, cur_col = p_day, p_col
    else:
        year_col = str(datetime.now().year)
        col_to_use = year_col if year_col in df.columns else df.columns[-1]
        for i in range(1, num_patterns + 1):
            idx = row_idx - i
            if idx >= 0:
                val = df.iloc[idx][col_to_use]
                patterns.append(val[-2:] if len(val) >= 2 else '')
            else:
                patterns.append('')
                
    patterns.reverse()
    return patterns, pattern_months

def scan_cau(df, patterns, num_patterns, exact_match, is_year_data, pattern_months, selected_month):
    results = {}
    cau_positions = set()
    predict_positions = set()
    
    ignore_cols = ['Ngày']
    if is_year_data:
        search_cols = [c for c in df.columns if c not in pattern_months and c not in ignore_cols and c != selected_month]
    else:
        current_year_col = str(datetime.now().year)
        search_cols = [c for c in df.columns if c != current_year_col and c not in ignore_cols]

    directions = [("Trên xuống (↓)", True), ("Dưới lên (↑)", False)]

    for step in range(6):
        gap = step + 1
        for dir_label, inside in directions:
            count = 0
            result_vals = []
            key = f"{dir_label} - Cách {step}"
            
            for col in search_cols:
                for i in range(len(df)):
                    if inside: 
                        if i <= len(df) - num_patterns * gap:
                            ok = True
                            positions_temp = []
                            for k in range(num_patterns):
                                val = df.iloc[i + k*gap][col]
                                if not matches_last_two_digits(val, patterns[k], exact_match):
                                    ok = False; break
                                positions_temp.append((i + k*gap, col))
                            
                            if ok:
                                pred_idx = i + (num_patterns - 1)*gap + gap
                                if 0 <= pred_idx < len(df):
                                    pred_val = df.iloc[pred_idx][col]
                                    if pred_val:
                                        count += 1
                                        result_vals.append(pred_val)
                                        cau_positions.update(positions_temp)
                                        predict_positions.add((pred_idx, col))
                    else: 
                        if i >= (num_patterns - 1) * gap:
                            ok = True
                            positions_temp = []
                            for k in range(num_patterns):
                                val = df.iloc[i - k*gap][col]
                                if not matches_last_two_digits(val, patterns[k], exact_match):
                                    ok = False; break
                                positions_temp.append((i - k*gap, col))
                                
                            if ok:
                                pred_idx = i - (num_patterns - 1)*gap - gap
                                if 0 <= pred_idx < le
