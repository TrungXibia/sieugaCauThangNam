import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from collections import Counter
import itertools
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

# --- BẢNG MÀU PASTEL ---
COLORS = ['#ffcccc', '#ccffcc', '#ccccff', '#ffcc99', '#99ccff', '#ff99cc']
CAU_COLOR = '#ffff99'
PREDICT_COLOR = '#ff4b4b'

# =============================================================================
# HÀM XỬ LÝ DỮ LIỆU
# =============================================================================


def generate_digital_combinations(val_str, length):
    """Tạo tất cả các số có độ dài 'length' từ các chữ số trong val_str."""
    digits = sorted(list(set(filter(str.isdigit, str(val_str)))))
    if not digits: return []
    return [''.join(p) for p in itertools.product(digits, repeat=length)]

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

# --- HÀM SO KHỚP ---
def find_pattern_position(value, pattern, allow_reverse=False):
    val_str = str(value).strip()
    if not val_str or not pattern:
        return -1
    
    pat_len = len(pattern)
    patterns_to_check = [pattern]
    if allow_reverse and pattern != pattern[::-1]:
        patterns_to_check.append(pattern[::-1])
    
    for i in range(len(val_str) - pat_len + 1):
        if val_str[i:i+pat_len] in patterns_to_check:
            return i
    return -1

def matches_pattern_logic(value, pattern, exact=False, position=None, allow_reverse=False):
    val_str = str(value).strip()
    if not val_str or not pattern:
        return False

    pat_len = len(pattern)
    if exact:
        # Validate unique digit count: value must have at least as many unique digits as pattern
        pattern_unique_count = len(set(pattern))
        val_unique_count = len(set(val_str))
        if val_unique_count < pattern_unique_count:
            return False
        
        patterns_to_check = [pattern]
        if allow_reverse:
            # Nếu là 3D (độ dài 3), lấy tất cả hoán vị (Tam hợp)
            if len(pattern) == 3:
                perms = [''.join(p) for p in itertools.permutations(pattern)]
                patterns_to_check = list(set(perms))
            elif pattern != pattern[::-1]:
                patterns_to_check.append(pattern[::-1])
        
        if position is not None:
            if isinstance(position, (list, tuple)):
                match_val = "".join([val_str[i] for i in position if 0 <= i < len(val_str)])
                if len(match_val) < pat_len: return False
                return match_val in patterns_to_check
            else:
                if position < 0 or position >= len(val_str) - pat_len + 1:
                    return False
                return val_str[position:position+pat_len] in patterns_to_check
        
        for i in range(len(val_str) - pat_len + 1):
            if val_str[i:i+pat_len] in patterns_to_check:
                return True
        return False
    else:
        # "Có chứa" logic: ensure all characters in pattern are present in value
        temp_val = val_str
        for char in pattern:
            if char in temp_val:
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

def get_patterns(df, is_year_data, row_idx, col_name, num_patterns, is_3d=False):
    patterns = []
    pattern_months = set()
    pat_len = 3 if is_3d else 2
    
    if is_year_data:
        cur_day, cur_col = row_idx, col_name
        for _ in range(num_patterns):
            p_day, p_col = get_prev_cell_year(df, cur_day, cur_col)
            if p_day < 0 or not p_col:
                patterns.append('')
            else:
                val = df.iloc[p_day][p_col]
                patterns.append(val[-pat_len:] if len(val) >= pat_len else '')
                pattern_months.add(p_col)
                cur_day, cur_col = p_day, p_col
    else:
        year_col = str(datetime.now().year)
        col_to_use = year_col if year_col in df.columns else df.columns[-1]
        for i in range(1, num_patterns + 1):
            idx = row_idx - i
            if idx >= 0:
                val = df.iloc[idx][col_to_use]
                patterns.append(val[-pat_len:] if len(val) >= pat_len else '')
            else:
                patterns.append('')
                
    patterns.reverse()
    return patterns, pattern_months

def scan_cau(df, patterns, num_patterns, exact_match, is_year_data, pattern_months, selected_month, target_step=None, allow_reverse=False):
    results = {}
    cau_positions = set()
    predict_positions = set()
    
    # Get pattern length from first pattern
    pat_len = len(patterns[0]) if patterns and patterns[0] else 2
    
    ignore_cols = ['Ngày']
    if is_year_data:
        search_cols = [c for c in df.columns if c not in pattern_months and c not in ignore_cols and c != selected_month]
    else:
        current_year_col = str(datetime.now().year)
        search_cols = [c for c in df.columns if c != current_year_col and c not in ignore_cols]

    directions = [("Trên xuống (↓)", True), ("Dưới lên (↑)", False)]

    for step in range(6):
        if target_step is not None and step != target_step:
            continue

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
                            fixed_position = None
                            
                            # Logic for Exact Match with Exhaustive Positions (Non-contiguous)
                            if exact_match:
                                first_val = str(df.iloc[i][col]).strip()
                                index_combinations = list(itertools.combinations(range(len(first_val)), pat_len))
                                
                                found_bridge = False
                                for pos_tuple in index_combinations:
                                    ok_tuple = True
                                    for k in range(num_patterns):
                                        val = str(df.iloc[i + k*gap][col]).strip()
                                        if not matches_pattern_logic(val, patterns[k], exact=True, position=pos_tuple, allow_reverse=allow_reverse):
                                            ok_tuple = False
                                            break
                                    if ok_tuple:
                                        fixed_position = pos_tuple
                                        found_bridge = True
                                        break
                                if not found_bridge: ok = False
                            
                            for k in range(num_patterns):
                                if not ok: break
                                if not exact_match:
                                    val = df.iloc[i + k*gap][col]
                                    if not matches_pattern_logic(val, patterns[k], exact_match, None, allow_reverse):
                                        ok = False
                                        break
                                        
                                positions_temp.append((i + k*gap, col))
                            
                            if ok:
                                pred_idx = i + (num_patterns - 1)*gap + gap
                                if 0 <= pred_idx < len(df):
                                    pred_val = df.iloc[pred_idx][col]
                                    if pred_val:
                                        count += 1
                                    result_vals.append({
                                        'value': pred_val,
                                        'predict_pos': (pred_idx, col),
                                        'cau_pos': positions_temp,
                                        'match_position': fixed_position if exact_match else None
                                    })
                                    cau_positions.update(positions_temp)
                                    predict_positions.add((pred_idx, col))
                    else: 
                        if i >= (num_patterns - 1) * gap:
                            ok = True
                            positions_temp = []
                            fixed_position = None
                            
                            if exact_match:
                                first_val = str(df.iloc[i][col]).strip()
                                index_combinations = list(itertools.combinations(range(len(first_val)), pat_len))
                                
                                found_bridge = False
                                for pos_tuple in index_combinations:
                                    ok_tuple = True
                                    for k in range(num_patterns):
                                        val = str(df.iloc[i - k*gap][col]).strip()
                                        if not matches_pattern_logic(val, patterns[k], exact=True, position=pos_tuple, allow_reverse=allow_reverse):
                                            ok_tuple = False
                                            break
                                    if ok_tuple:
                                        fixed_position = pos_tuple
                                        found_bridge = True
                                        break
                                if not found_bridge: ok = False

                            for k in range(num_patterns):
                                if not ok: break
                                if not exact_match:
                                    val = df.iloc[i - k*gap][col]
                                    if not matches_pattern_logic(val, patterns[k], exact_match, None, allow_reverse):
                                        ok = False
                                        break
                                        
                                positions_temp.append((i - k*gap, col))
                                
                            if ok:
                                pred_idx = i - (num_patterns - 1)*gap - gap
                                if 0 <= pred_idx < len(df):
                                    pred_val = df.iloc[pred_idx][col]
                                    if pred_val:
                                        count += 1
                                    result_vals.append({
                                        'value': pred_val,
                                        'predict_pos': (pred_idx, col),
                                        'cau_pos': positions_temp,
                                        'match_position': fixed_position if exact_match else None
                                    })
                                    cau_positions.update(positions_temp)
                                    predict_positions.add((pred_idx, col))
            
            pairs = []
            pat_len = len(patterns[0]) if patterns and patterns[0] else 2
            for item in result_vals:
                val = item['value']
                pos = item.get('match_position')
                if pos is not None:
                    if isinstance(pos, (list, tuple)):
                        extracted = "".join([val[i] for i in pos if 0 <= i < len(val)])
                        if len(extracted) == pat_len:
                            pairs.append(extracted)
                    elif 0 <= pos < len(val) - pat_len + 1:
                        pairs.append(val[pos:pos+pat_len])
                else:
                    pairs.extend(generate_digital_combinations(val, pat_len))

            results[key] = {
                'count': count,
                'items': result_vals,
                'pairs': pairs
            }

    return results, cau_positions, predict_positions

def scan_cau_horizontal(df, patterns, num_patterns, exact_match, is_year_data, pattern_months, selected_month, pattern_row_idx, target_step=None, allow_reverse=False):
    """
    Tìm cầu theo chiều ngang (trái/phải theo cột).
    Cột chứa pattern (pattern source column) sẽ được loại trừ.
    """
    results = {}
    cau_positions = set()
    predict_positions = set()
    
    # Get pattern length from first pattern
    pat_len = len(patterns[0]) if patterns and patterns[0] else 2
    
    ignore_cols = ['Ngày']
    
    # Xác định cột pattern source để loại trừ
    if is_year_data:
        pattern_source_col = selected_month
        search_cols = [c for c in df.columns if c not in pattern_months and c not in ignore_cols and c != selected_month]
    else:
        pattern_source_col = str(datetime.now().year)
        search_cols = [c for c in df.columns if c != pattern_source_col and c not in ignore_cols]
    
    # Lấy index của các cột để tìm ngang
    all_cols = [col for col in df.columns if col not in ignore_cols]
    
    directions = [("Trái sang phải (→)", True), ("Phải sang trái (←)", False)]

    for step in range(6):
        if target_step is not None and step != target_step:
            continue

        gap = step + 1
        for dir_label, forward in directions:
            count = 0
            result_vals = []
            key = f"{dir_label} - Cách {step}"
            
            # Duyệt qua từng hàng (ngày)
            for row_idx in range(len(df)):
                # Duyệt qua các cột
                for col_start_idx in range(len(all_cols)):
                    start_col = all_cols[col_start_idx]
                    
                    # Bỏ qua nếu bắt đầu từ cột pattern source
                    if start_col == pattern_source_col:
                        continue
                    
                    if forward:  # Trái sang phải
                        if col_start_idx + (num_patterns - 1) * gap + gap >= len(all_cols):
                            continue
                        
                        ok = True
                        positions_temp = []
                        fixed_position = None
                        
                        for k in range(num_patterns):
                            col_idx = col_start_idx + k * gap
                            if col_idx >= len(all_cols):
                                ok = False
                                break
                            
                            col = all_cols[col_idx]
                            if col == pattern_source_col:
                                ok = False
                                break
                                
                            val = df.iloc[row_idx][col]
                            
                            if exact_match:
                                if k == 0:
                                    fixed_position = find_pattern_position(val, patterns[k], allow_reverse)
                                    if fixed_position == -1:
                                        ok = False
                                        break
                                else:
                                    if not matches_pattern_logic(val, patterns[k], exact_match, fixed_position, allow_reverse):
                                        ok = False
                                        break
                            else:
                                if not matches_pattern_logic(val, patterns[k], exact_match, None, allow_reverse):
                                    ok = False
                                    break
                                    
                            positions_temp.append((row_idx, col))
                        
                        if ok:
                            pred_col_idx = col_start_idx + (num_patterns - 1) * gap + gap
                            if 0 <= pred_col_idx < len(all_cols):
                                pred_col = all_cols[pred_col_idx]
                                if pred_col != pattern_source_col:
                                    pred_val = df.iloc[row_idx][pred_col]
                                    if pred_val:
                                        count += 1
                                    result_vals.append({
                                        'value': pred_val,
                                        'predict_pos': (row_idx, pred_col),
                                        'cau_pos': positions_temp,
                                        'match_position': fixed_position if exact_match else None
                                    })
                                    cau_positions.update(positions_temp)
                                    predict_positions.add((row_idx, pred_col))
                    
                    else:  # Phải sang trái
                        if col_start_idx - (num_patterns - 1) * gap - gap < 0:
                            continue
                        
                        ok = True
                        positions_temp = []
                        fixed_position = None
                        
                        for k in range(num_patterns):
                            col_idx = col_start_idx - k * gap
                            if col_idx < 0:
                                ok = False
                                break
                            
                            col = all_cols[col_idx]
                            if col == pattern_source_col:
                                ok = False
                                break
                                
                            val = df.iloc[row_idx][col]
                            
                            if exact_match:
                                if k == 0:
                                    fixed_position = find_pattern_position(val, patterns[k], allow_reverse)
                                    if fixed_position == -1:
                                        ok = False
                                        break
                                else:
                                    if not matches_pattern_logic(val, patterns[k], exact_match, fixed_position, allow_reverse):
                                        ok = False
                                        break
                            else:
                                if not matches_pattern_logic(val, patterns[k], exact_match, None, allow_reverse):
                                    ok = False
                                    break
                                    
                            positions_temp.append((row_idx, col))
                            
                        if ok:
                            pred_col_idx = col_start_idx - (num_patterns - 1) * gap - gap
                            if 0 <= pred_col_idx < len(all_cols):
                                pred_col = all_cols[pred_col_idx]
                                if pred_col != pattern_source_col:
                                    pred_val = df.iloc[row_idx][pred_col]
                                    if pred_val:
                                        count += 1
                                    result_vals.append({
                                        'value': pred_val,
                                        'predict_pos': (row_idx, pred_col),
                                        'cau_pos': positions_temp,
                                        'match_position': fixed_position if exact_match else None
                                    })
                                    cau_positions.update(positions_temp)
                                    predict_positions.add((row_idx, pred_col))
            
            pairs = []
            pat_len = len(patterns[0]) if patterns and patterns[0] else 2
            for item in result_vals:
                val = item['value']
                pos = item.get('match_position')
                if pos is not None:
                    if isinstance(pos, (list, tuple)):
                        extracted = "".join([val[i] for i in pos if 0 <= i < len(val)])
                        if len(extracted) == pat_len:
                            pairs.append(extracted)
                    elif 0 <= pos < len(val) - pat_len + 1:
                        pairs.append(val[pos:pos+pat_len])
                else:
                    pairs.extend(generate_digital_combinations(val, pat_len))

            results[key] = {
                'count': count,
                'items': result_vals,
                'pairs': pairs
            }

    return results, cau_positions, predict_positions

# =============================================================================
# GIAO DIỆN CHÍNH
# =============================================================================

def main():
    if 'exact_match_state' not in st.session_state:
        st.session_state.exact_match_state = False
    if 'contains_both_state' not in st.session_state:
        st.session_state.contains_both_state = True
    if 'allow_reverse_state' not in st.session_state:
        st.session_state.allow_reverse_state = False

    def toggle_exact_match():
        if st.session_state.exact_match_state:
            st.session_state.contains_both_state = False

    def toggle_contains_both():
        if st.session_state.contains_both_state:
            st.session_state.exact_match_state = False

    # --- SIDEBAR ---
    st.sidebar.title("⚙️ Điều khiển")
    
    data_mode = st.sidebar.radio("Chế độ dữ liệu", ["Tháng", "Năm"])
    is_year_data = (data_mode == "Năm")
    
    if st.sidebar.button("🔄 Lấy dữ liệu mới"):
        st.cache_data.clear()
        st.rerun()

    df = fetch_data('year' if is_year_data else 'month')
    
    if df is None:
        st.warning("Chưa có dữ liệu. Vui lòng tải lại.")
        return

    st.sidebar.markdown("---")
    st.sidebar.subheader("Cấu hình tìm cầu")
    
    # Lấy ngày và giờ hiện tại
    current_datetime = datetime.now()
    current_day = current_datetime.day
    current_hour = current_datetime.hour
    current_minute = current_datetime.minute
    
    days = [str(i) for i in range(1, len(df) + 1)]
    
    # Nếu sau 18h30, chọn ngày tiếp theo
    if current_hour > 18 or (current_hour == 18 and current_minute >= 30):
        default_day = current_day + 1
    else:
        default_day = current_day
    
    # Đảm bảo ngày mặc định không vượt quá số ngày có trong dữ liệu
    if default_day > len(days):
        default_day = len(days)
    
    # Tìm index của ngày mặc định
    default_index = len(days) - 1
    if str(default_day) in days:
        default_index = days.index(str(default_day))
    elif str(current_day) in days:
        default_index = days.index(str(current_day))
    
    selected_day = st.sidebar.selectbox("Chọn ngày", days, index=default_index)
    row_idx = int(selected_day) - 1
    
    selected_month = None
    if is_year_data:
        months = [c for c in df.columns if c.startswith("TH")]
        cur_m_idx = datetime.now().month - 1
        if cur_m_idx < len(months):
             def_m = months[cur_m_idx]
        else: def_m = months[0]
        selected_month = st.sidebar.selectbox("Chọn cột tháng (để lấy mẫu)", months, index=months.index(def_m) if def_m in months else 0)
    
    num_patterns = st.sidebar.number_input("Số ngày chạy cầu", min_value=1, max_value=5, value=2)
    
    st.sidebar.text("Kiểu so khớp:")
    st.sidebar.checkbox("Chính xác mẫu (cùng vị trí)", key='exact_match_state', on_change=toggle_exact_match)
    st.sidebar.checkbox("Có chứa (Kép cần 1, Lệch cần 2)", key='contains_both_state', on_change=toggle_contains_both)
    st.sidebar.checkbox("🔄 Tìm đảo (30 ↔ 03)", key='allow_reverse_state')
    st.sidebar.checkbox("🎯 Chế độ 3D (Tìm 3 số)", key='is_3d_state')
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Hướng tìm cầu:**")
    if 'search_direction' not in st.session_state:
        st.session_state.search_direction = "Lên Xuống"
    search_direction = st.sidebar.radio(
        "Hướng tìm", 
        ["↕ Lên Xuống (theo ngày)", "↔ Trái Phải (theo cột)", "↕↔ Cả hai (Cùng lúc)"],
        key='search_direction_radio',
        label_visibility="collapsed"
    )
    is_horizontal = "Trái Phải" in search_direction
    is_both = "Cả hai" in search_direction
    
    exact_match = st.session_state.exact_match_state
    allow_reverse = st.session_state.allow_reverse_state

    col_pattern_source = selected_month if is_year_data else str(datetime.now().year)
    is_3d = st.session_state.get('is_3d_state', False)
    patterns, pattern_months = get_patterns(df, is_year_data, row_idx, col_pattern_source, num_patterns, is_3d=is_3d)
    
    st.sidebar.markdown("#### Mẫu hiện tại:")
    for i, p in enumerate(patterns):
        if allow_reverse and p:
            if len(p) == 3:
                p_set = sorted(list(set(p)))
                perms = sorted(list(set([''.join(perm) for perm in itertools.product(p_set, repeat=len(p))])))
                # perms_actual = sorted(list(set([''.join(perm) for perm in itertools.product(p_set, repeat=len(p))])))

                if p in perms: perms.remove(p)
                if perms:
                    st.sidebar.code(f"Mẫu {i+1}: {p} hoặc {', '.join(perms)}")
                else:
                    st.sidebar.code(f"Mẫu {i+1}: {p}")
            elif p != p[::-1]:
                st.sidebar.code(f"Mẫu {i+1}: {p} hoặc {p[::-1]}")
            else:
                st.sidebar.code(f"Mẫu {i+1}: {p}")
        else:
            st.sidebar.code(f"Mẫu {i+1}: {p}")

    # --- TABS ---
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "📊 Dữ liệu & Cầu"
    
    def on_tab_change():
        st.session_state.active_tab = st.session_state.nav_radio

    st.radio(
        "", 
        ["📊 Dữ liệu & Cầu", "📈 Thống kê mức số", "🔍 Kiểm tra số"], 
        key="nav_radio", 
        index=["📊 Dữ liệu & Cầu", "📈 Thống kê mức số", "🔍 Kiểm tra số"].index(st.session_state.active_tab),
        horizontal=True,
        on_change=on_tab_change,
        label_visibility="collapsed"
    )
    
    active_tab = st.session_state.active_tab

    # --- TAB 1 ---
    if active_tab == "📊 Dữ liệu & Cầu":
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.subheader(f"Bảng kết quả ({data_mode})")
        with col2:
            step_options = ["Tất cả các cách"] + [f"Cách {i}" for i in range(6)]
            
            if 'selected_step_index' not in st.session_state:
                st.session_state.selected_step_index = 0

            def on_step_change():
                st.session_state.selected_step_index = step_options.index(st.session_state.step_selectbox)

            selected_step_label = st.selectbox(
                "Chọn cách soi", 
                step_options, 
                index=st.session_state.selected_step_index,
                key='step_selectbox',
                on_change=on_step_change
            )
            
            target_step = None
            if selected_step_label != "Tất cả các cách":
                target_step = int(selected_step_label.split(" ")[1])
        with col3:
            view_mode = st.selectbox("Chế độ xem", ["Highlight Cầu", "Dữ liệu gốc"])

        # Tính toán số dự đoán theo cách đã chọn
        if is_both:
            res_v, cp_v, pp_v = scan_cau(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, 
                target_step=target_step, allow_reverse=allow_reverse
            )
            res_h, cp_h, pp_h = scan_cau_horizontal(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, row_idx,
                target_step=target_step, allow_reverse=allow_reverse
            )
            results_for_prediction = {**res_v, **res_h}
            # Note: cau_pos and pred_pos are not used here for calculation, but for consistency if needed later
        elif is_horizontal:
            results_for_prediction, _, _ = scan_cau_horizontal(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, row_idx,
                target_step=target_step, allow_reverse=allow_reverse
            )
        else:
            results_for_prediction, _, _ = scan_cau(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, 
                target_step=target_step, allow_reverse=allow_reverse
            )
        
        # Lấy số dự đoán từ kết quả theo cách đã chọn
        predicted_numbers_filtered = set()
        for key, data in results_for_prediction.items():
            for p in data.get('pairs', []):
                if p:
                    predicted_numbers_filtered.add(p)
                    if allow_reverse:
                        if len(p) == 3:
                            perms = [''.join(perm) for perm in itertools.permutations(p)]
                            for perm in perms:
                                predicted_numbers_filtered.add(perm)
                        elif p != p[::-1]:
                            predicted_numbers_filtered.add(p[::-1])

        # Hiển thị số dự đoán ở đầu
        if predicted_numbers_filtered:
            sorted_predictions = sorted(list(predicted_numbers_filtered))
            predictions_text = ', '.join(sorted_predictions)
            st.success(f"🎯 **Dự đoán ({selected_step_label}) - {len(predicted_numbers_filtered)} số:** {predictions_text}")
            st.markdown("---")

        if is_both:
            res_v, cp_v, pp_v = scan_cau(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, 
                target_step=target_step, allow_reverse=allow_reverse
            )
            res_h, cp_h, pp_h = scan_cau_horizontal(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, row_idx,
                target_step=target_step, allow_reverse=allow_reverse
            )
            results = {**res_v, **res_h}
            cau_pos = cp_v.union(cp_h)
            pred_pos = pp_v.union(pp_h)
        elif is_horizontal:
            results, cau_pos, pred_pos = scan_cau_horizontal(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, row_idx,
                target_step=target_step, allow_reverse=allow_reverse
            )
        else:
            results, cau_pos, pred_pos = scan_cau(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, 
                target_step=target_step, allow_reverse=allow_reverse
            )

        highlight_target = st.session_state.get('highlight_target', None)
        
        if highlight_target:
            view_mode = "Highlight Cầu"
            if st.button("❌ Xóa Highlight đang chọn"):
                st.session_state.highlight_target = None
                st.rerun()

        if view_mode == "Highlight Cầu":
            match_text = "Cùng vị trí (2 số liên tiếp)" if exact_match else "Toàn bộ số (Kép cần 1, Lệch cần 2)"
            if allow_reverse:
                match_text += " + Tìm đảo"
            st.caption(f"Chế độ: {match_text} | {selected_step_label}")
            
            def highlight_cells(x):
                df_css = pd.DataFrame('', index=x.index, columns=x.columns)
                
                if highlight_target:
                    tr, tc = highlight_target['predict_pos']
                    df_css.at[tr, tc] = f'background-color: #FF0000; color: #FFFF00; font-weight: bold; border: 3px solid #FFFF00'
                    
                    for pr, pc in highlight_target['cau_pos']:
                        df_css.at[pr, pc] = f'background-color: #FF4500; color: white; font-weight: bold; border: 2px solid #FFFF00'
                    
                    return df_css

                # Pattern highlights - REMOVED to reduce noise
                pass
                
                if is_year_data:
                    cur_d, cur_c = row_idx, selected_month
                    for i in range(num_patterns):
                         pd_idx, pc_idx = get_prev_cell_year(df, cur_d, cur_c)
                         if pd_idx >= 0:
                             df_css.at[pd_idx, pc_idx] = f'background-color: {COLORS[(num_patterns-1-i) % len(COLORS)]}; color: black'
                             cur_d, cur_c = pd_idx, pc_idx
                else:
                    y_col = str(datetime.now().year)
                    if y_col in df.columns:
                        for i in range(1, num_patterns + 1):
                            idx = row_idx - i
                            if idx >= 0:
                                df_css.at[idx, y_col] = f'background-color: {COLORS[(num_patterns-i) % len(COLORS)]}; color: black'

                for r_idx, c_name in cau_pos:
                    if (r_idx, c_name) not in pred_pos:
                        df_css.at[r_idx, c_name] = f'background-color: {CAU_COLOR}; color: black'
                
                for r_idx, c_name in pred_pos:
                    df_css.at[r_idx, c_name] = f'background-color: {PREDICT_COLOR}; color: white; font-weight: bold'

                return df_css

            st.dataframe(df.style.apply(highlight_cells, axis=None), height=600, use_container_width=True)
        else:
            st.dataframe(df, height=600, use_container_width=True)

    # --- TAB 2 ---
    elif active_tab == "📈 Thống kê mức số":
        step_options = ["Tất cả các cách"] + [f"Cách {i}" for i in range(6)]
        current_idx = st.session_state.get('selected_step_index', 0)
        selected_step_label = step_options[current_idx]
        
        target_step = None
        if selected_step_label != "Tất cả các cách":
            target_step = int(selected_step_label.split(" ")[1])

        if is_both:
            res_v, cp_v, pp_v = scan_cau(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, 
                target_step=target_step, allow_reverse=allow_reverse
            )
            res_h, cp_h, pp_h = scan_cau_horizontal(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, row_idx,
                target_step=target_step, allow_reverse=allow_reverse
            )
            results = {**res_v, **res_h}
            cau_pos = cp_v.union(cp_h)
            pred_pos = pp_v.union(pp_h)
        elif is_horizontal:
            results, cau_pos, pred_pos = scan_cau_horizontal(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, row_idx,
                target_step=target_step, allow_reverse=allow_reverse
            )
        else:
            results, cau_pos, pred_pos = scan_cau(
                df, patterns, num_patterns, exact_match, 
                is_year_data, pattern_months, selected_month, 
                target_step=target_step, allow_reverse=allow_reverse
            )

        st.subheader(f"Thống kê: {selected_step_label}")
        
        col_left, col_right = st.columns([1, 1])
        final_pairs_bag = []
        
        with col_left:
            st.markdown("#### Chi tiết từng cách")
            if not results:
                 st.info("Không tìm thấy cầu nào cho lựa chọn này.")
            
            for key, data in results.items():
                with st.expander(f"{key} ({data['count']} cầu)", expanded=True):
                    if data['count'] > 0:
                        cols = st.columns(8)
                        for idx, item in enumerate(data['items']):
                            val = item['value']
                            with cols[idx % 8]:
                                if st.button(val, key=f"btn_{key}_{idx}"):
                                    st.session_state.highlight_target = item
                                    st.session_state.active_tab = "📊 Dữ liệu & Cầu"
                                    st.rerun()
                        
                        if st.checkbox(f"Gộp {key}", value=True, key=f"chk_{key}"):
                            final_pairs_bag.extend(data['pairs'])
                    else:
                        st.write("Không có cầu.")
        
        with col_right:
            st.markdown("#### Tổng hợp mức số")
            
            levels_text = ""
            if final_pairs_bag:
                counts = Counter(final_pairs_bag)
                sorted_levels = sorted(set(counts.values()), reverse=True)
                for lvl in sorted_levels:
                    nums = sorted([k for k, v in counts.items() if v == lvl])
                    if nums:
                        line = f"**Mức {lvl}** ({len(nums)} số): {', '.join(nums)}"
                        st.markdown(line)
                        levels_text += f"Mức {lvl} ({len(nums)} số): {','.join(nums)}\n"
            else:
                st.info("Chưa có số liệu.")

            is_3d = st.session_state.get('is_3d_state', False)
            all_possible = set(f"{i:03d}" if is_3d else f"{i:02d}" for i in (range(1000) if is_3d else range(100)))
            found_numbers = set(final_pairs_bag) if final_pairs_bag else set()
            missing_numbers = sorted(list(all_possible - found_numbers))
            
            if missing_numbers:
                st.markdown("---")
                st.markdown(f"**Mức 0** (Không xuất hiện - {len(missing_numbers)} số):")
                st.code(', '.join(missing_numbers))
                levels_text += f"Mức 0 ({len(missing_numbers)} số): {','.join(missing_numbers)}\n"
            
            st.text_area("Copy kết quả:", value=levels_text, height=300)

    # --- TAB 3 ---
    elif active_tab == "🔍 Kiểm tra số":
        st.subheader("Kiểm tra mức độ xuất hiện của một số")
        is_3d = st.session_state.get('is_3d_state', False)
        expected_len = 3 if is_3d else 2
        check_num = st.text_input(f"Nhập số ({expected_len} chữ số):", max_chars=expected_len)
        
        if st.button("Kiểm tra") and check_num:
            expected_len = 3 if st.session_state.get('is_3d_state', False) else 2
            if not check_num.isdigit() or len(check_num) != expected_len:
                st.error(f"Vui lòng nhập {expected_len} chữ số.")
            else:
                if is_both:
                    res_v, cp_v, pp_v = scan_cau(
                        df, patterns, num_patterns, exact_match, 
                        is_year_data, pattern_months, selected_month, 
                        target_step=None, allow_reverse=allow_reverse
                    )
                    res_h, cp_h, pp_h = scan_cau_horizontal(
                        df, patterns, num_patterns, exact_match, 
                        is_year_data, pattern_months, selected_month, row_idx,
                        target_step=None, allow_reverse=allow_reverse
                    )
                    results = {**res_v, **res_h}
                    # Templates are tricky here, we'll use a combined approach below
                    key_v_forward = "Trên xuống (↓) - Cách {}"
                    key_v_backward = "Dưới lên (↑) - Cách {}"
                    key_h_forward = "Trái sang phải (→) - Cách {}"
                    key_h_backward = "Phải sang trái (←) - Cách {}"
                elif is_horizontal:
                    results, cau_pos, pred_pos = scan_cau_horizontal(
                        df, patterns, num_patterns, exact_match, 
                        is_year_data, pattern_months, selected_month, row_idx,
                        target_step=None, allow_reverse=allow_reverse
                    )
                    key_forward_template = "Trái sang phải (→) - Cách {}"
                    key_backward_template = "Phải sang trái (←) - Cách {}"
                else:
                    results, cau_pos, pred_pos = scan_cau(
                        df, patterns, num_patterns, exact_match, 
                        is_year_data, pattern_months, selected_month, 
                        target_step=None, allow_reverse=allow_reverse
                    )
                    key_forward_template = "Trên xuống (↓) - Cách {}"
                    key_backward_template = "Dưới lên (↑) - Cách {}"

                data_check = []
                steps_to_check = range(6)
                
                for step in steps_to_check:
                    if is_both:
                        # Combine counts from both directions
                        c_vf = Counter(results.get(key_v_forward.format(step), {}).get('pairs', []))
                        c_vb = Counter(results.get(key_v_backward.format(step), {}).get('pairs', []))
                        c_hf = Counter(results.get(key_h_forward.format(step), {}).get('pairs', []))
                        c_hb = Counter(results.get(key_h_backward.format(step), {}).get('pairs', []))
                        
                        count_forward = c_vf.get(check_num, 0) + c_hf.get(check_num, 0)
                        count_backward = c_vb.get(check_num, 0) + c_hb.get(check_num, 0)
                    else:
                        key_forward = key_forward_template.format(step)
                        count_forward = 0
                        if key_forward in results:
                            pairs = results[key_forward]['pairs']
                            c = Counter(pairs)
                            count_forward = c.get(check_num, 0)
                        
                        key_backward = key_backward_template.format(step)
                        count_backward = 0
                        if key_backward in results:
                            pairs = results[key_backward]['pairs']
                            c = Counter(pairs)
                            count_backward = c.get(check_num, 0)
                        
                    data_check.append({
                        "Cách": f"Cách {step}",
                        "Mức (→/↓)": count_forward,
                        "Mức (←/↑)": count_backward
                    })
                
                st.table(pd.DataFrame(data_check))

if __name__ == "__main__":
    main()
