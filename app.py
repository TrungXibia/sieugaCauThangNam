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

# --- BẢNG MÀU PASTEL ---
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

# --- HÀM SO KHỚP ---
def find_pattern_position(value, pattern, allow_reverse=False):
    val_str = str(value).strip()
    if not val_str or not pattern or len(pattern) != 2:
        return -1
    
    patterns_to_check = [pattern]
    if allow_reverse and pattern[0] != pattern[1]:
        patterns_to_check.append(pattern[::-1])
    
    for i in range(len(val_str) - 1):
        if val_str[i:i+2] in patterns_to_check:
            return i
    return -1

def matches_last_two_digits(value, pattern, exact=False, position=None, allow_reverse=False):
    val_str = str(value).strip()
    if not val_str or not pattern:
        return False

    if exact:
        if len(pattern) != 2:
            return False
        
        patterns_to_check = [pattern]
        if allow_reverse and pattern[0] != pattern[1]:
            patterns_to_check.append(pattern[::-1])
        
        if position is not None:
            if position < 0 or position >= len(val_str) - 1:
                return False
            return val_str[position:position+2] in patterns_to_check
        
        for i in range(len(val_str) - 1):
            if val_str[i:i+2] in patterns_to_check:
                return True
        return False
    else:
        if pattern[0] == pattern[1]:
            return pattern[0] in val_str
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

def scan_cau(df, patterns, num_patterns, exact_match, is_year_data, pattern_months, selected_month, target_step=None, allow_reverse=False):
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
                            
                            for k in range(num_patterns):
                                val = df.iloc[i + k*gap][col]
                                
                                if exact_match:
                                    if k == 0:
                                        fixed_position = find_pattern_position(val, patterns[k], allow_reverse)
                                        if fixed_position == -1:
                                            ok = False
                                            break
                                    else:
                                        if not matches_last_two_digits(val, patterns[k], exact_match, fixed_position, allow_reverse):
                                            ok = False
                                            break
                                else:
                                    if not matches_last_two_digits(val, patterns[k], exact_match, None, allow_reverse):
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
                                        'cau_pos': positions_temp
                                    })
                                    cau_positions.update(positions_temp)
                                    predict_positions.add((pred_idx, col))
                    else: 
                        if i >= (num_patterns - 1) * gap:
                            ok = True
                            positions_temp = []
                            fixed_position = None
                            
                            for k in range(num_patterns):
                                val = df.iloc[i - k*gap][col]
                                
                                if exact_match:
                                    if k == 0:
                                        fixed_position = find_pattern_position(val, patterns[k], allow_reverse)
                                        if fixed_position == -1:
                                            ok = False
                                            break
                                    else:
                                        if not matches_last_two_digits(val, patterns[k], exact_match, fixed_position, allow_reverse):
                                            ok = False
                                            break
                                else:
                                    if not matches_last_two_digits(val, patterns[k], exact_match, None, allow_reverse):
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
                                        'cau_pos': positions_temp
                                    })
                                    cau_positions.update(positions_temp)
                                    predict_positions.add((pred_idx, col))
            
            pairs = []
            for item in result_vals:
                val = item['value']
                if len(val) >= 2: 
                    digits = list(val)
                    local_pairs = [a+b for a in digits for b in digits]
                    pairs.extend(local_pairs)

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
    
    current_day = datetime.now().day
    days = [str(i) for i in range(1, len(df) + 1)]
    
    default_index = len(days) - 1
    if str(current_day) in days:
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
    
    exact_match = st.session_state.exact_match_state
    allow_reverse = st.session_state.allow_reverse_state

    col_pattern_source = selected_month if is_year_data else str(datetime.now().year)
    patterns, pattern_months = get_patterns(df, is_year_data, row_idx, col_pattern_source, num_patterns)
    
    st.sidebar.markdown("#### Mẫu hiện tại:")
    for i, p in enumerate(patterns):
        if allow_reverse and p and p[0] != p[1]:
            st.sidebar.code(f"Mẫu {i+1}: {p} hoặc {p[::-1]}")
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
        results_for_prediction, _, _ = scan_cau(
            df, patterns, num_patterns, exact_match, 
            is_year_data, pattern_months, selected_month, 
            target_step=target_step, allow_reverse=allow_reverse
        )
        
        # Lấy 2 số cuối từ kết quả theo cách đã chọn
        predicted_numbers_filtered = set()
        for key, data in results_for_prediction.items():
            for item in data['items']:
                val = item['value']
                if len(val) >= 2:
                    last_two = val[-2:]
                    predicted_numbers_filtered.add(last_two)
                    if allow_reverse and last_two[0] != last_two[1]:
                        predicted_numbers_filtered.add(last_two[::-1])
        
        # Hiển thị số dự đoán ở đầu
        if predicted_numbers_filtered:
            st.markdown(f"### 🎯 Số dự đoán tiếp theo ({selected_step_label}):")
            sorted_predictions = sorted(list(predicted_numbers_filtered))
            predictions_text = ', '.join(sorted_predictions)
            st.text_area(
                f"Tổng: {len(predicted_numbers_filtered)} số", 
                value=predictions_text, 
                height=100
            )
            st.markdown("---")

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

                for col in x.columns:
                    if col == 'Ngày': continue
                    col_data = x[col]
                    for idx, val in col_data.items():
                        val_str = str(val)
                        for p_i in range(len(patterns)-1, -1, -1):
                            if matches_last_two_digits(val_str, patterns[p_i], exact_match, None, allow_reverse):
                                df_css.at[idx, col] = f'background-color: {COLORS[p_i % len(COLORS)]}; color: black'
                                break
                
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

            all_possible = set(f"{i:02d}" for i in range(100))
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
        check_num = st.text_input("Nhập số (2 chữ số):", max_chars=2)
        
        if st.button("Kiểm tra") and check_num:
            if not check_num.isdigit() or len(check_num) != 2:
                st.error("Vui lòng nhập 2 chữ số.")
            else:
                results, cau_pos, pred_pos = scan_cau(
                    df, patterns, num_patterns, exact_match, 
                    is_year_data, pattern_months, selected_month, 
                    target_step=None, allow_reverse=allow_reverse
                )

                data_check = []
                steps_to_check = range(6)
                
                for step in steps_to_check:
                    key_down = f"Trên xuống (↓) - Cách {step}"
                    count_down = 0
                    if key_down in results:
                        pairs = results[key_down]['pairs']
                        c = Counter(pairs)
                        count_down = c.get(check_num, 0)
                    
                    key_up = f"Dưới lên (↑) - Cách {step}"
                    count_up = 0
                    if key_up in results:
                        pairs = results[key_up]['pairs']
                        c = Counter(pairs)
                        count_up = c.get(check_num, 0)
                        
                    data_check.append({
                        "Cách": f"Cách {step}",
                        "Mức (↓)": count_down,
                        "Mức (↑)": count_up
                    })
                
                st.table(pd.DataFrame(data_check))

if __name__ == "__main__":
    main()

