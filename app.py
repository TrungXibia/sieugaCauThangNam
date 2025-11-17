import pandas as pd
from bs4 import BeautifulSoup
import requests
import warnings
from collections import Counter
from datetime import datetime
from io import StringIO
import json

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

warnings.filterwarnings("ignore", category=FutureWarning)

def _get_month_url():
    return 'https://congcuxoso.com/MienBac/DacBiet/PhoiCauDacBiet/PhoiCauThang5So.aspx'
def _get_year_url():
    return 'https://congcuxoso.com/MienBac/DacBiet/PhoiCauDacBiet/PhoiCauNam5So.aspx'
def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    cleaned_cols = {}
    for col_name in df.columns:
        if 'ngày' in str(col_name).lower():
            cleaned_cols[col_name] = df[col_name].astype(str).str.replace('.0', '', regex=False)
            continue
        def fmt(v):
            s = str(v).strip()
            if not s or s == '-----': return ''
            if s.endswith('.0'): s = s[:-2]
            return s.zfill(5)
        cleaned_cols[col_name] = df[col_name].map(fmt)
    new_df = pd.DataFrame(cleaned_cols)
    if 'Ngày.1' in new_df.columns: new_df = new_df.rename(columns={'Ngày.1': 'Ngày'})
    return new_df

def fetch_data_from_source(fetch_type='month'):
    try:
        sess = requests.Session()
        url = _get_month_url() if fetch_type == 'month' else _get_year_url()
        headers = {'User-Agent': 'Mozilla/5.0'}
        r1 = sess.get(url, timeout=20, headers=headers)
        r1.raise_for_status()
        soup = BeautifulSoup(r1.text, 'lxml')
        payload = {inp['name']: inp.get('value', '') for inp in soup.find_all('input', {'type': 'hidden'})}
        y = str(datetime.now().year)
        if fetch_type == 'month':
            m = str(datetime.now().month)
            payload.update({'ctl00$ContentPlaceHolder1$ddlThang': m, 'ctl00$ContentPlaceHolder1$ddlNam': y, 'ctl00$ContentPlaceHolder1$btnXem': 'Xem'})
        else:
            payload.update({'ctl00$ContentPlaceHolder1$ddlNam': y, 'ctl00$ContentPlaceHolder1$btnXem': 'Xem'})
        r2 = sess.post(url, data=payload, timeout=20, headers=headers)
        r2.raise_for_status()
        soup2 = BeautifulSoup(r2.text, 'lxml')
        keyword = 'Ngày' if fetch_type == 'month' else 'TH1'
        table = next(t for t in soup2.find_all('table') if t.find('tr') and keyword in t.find('tr').get_text())
        df = pd.read_html(StringIO(str(table)), header=0)[0].fillna('')
        return _clean_df(df)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

@app.route('/')
def home():
    return "Backend API is running."

@app.route('/fetch_data', methods=['POST'])
def api_fetch_data():
    data = request.get_json()
    fetch_type = data.get('type', 'month')
    df = fetch_data_from_source(fetch_type)
    if df is not None:
        return jsonify({
            'success': True, 'table_html': df.to_html(classes='table table-bordered text-center', index=False),
            'columns': list(df.columns), 'rows': len(df), 'df_json': df.to_json(orient='split'),
            'is_year_data': (fetch_type == 'year')
        })
    return jsonify({'success': False, 'message': f'Kết nối {fetch_type} thất bại.'})

@app.route('/run_analysis', methods=['POST'])
def api_run_analysis():
    data = request.get_json()
    df = pd.read_json(StringIO(data['df_json']), orient='split')
    is_year_data, row_idx, num_patterns, exact_match, selected_month_col, step_to_run = \
        data.get('is_year_data', False), int(data.get('day_idx', len(df) - 1)), int(data.get('num_patterns', 2)), \
        data.get('exact_match', False), data.get('month_col'), data.get('step')

    patterns, pattern_months = [], set()
    def _last_non_empty_row(col_name: str) -> int:
        if col_name not in df.columns: return -1
        col = df[col_name]
        for r in range(len(col)-1, -1, -1):
            v = col.iloc[r]
            if isinstance(v, str) and v.strip() != '': return r
        return -1
    def _prev_cell_year(day_idx: int, month_col: str):
        if day_idx > 0: return day_idx - 1, month_col
        m = int(month_col[2:])
        pm = 12 if m == 1 else m - 1
        pcol = f"TH{pm}"
        prow = _last_non_empty_row(pcol)
        return (prow, pcol) if prow >= 0 else (-1, pcol)
    
    if is_year_data:
        cur_day, cur_col = row_idx, selected_month_col
        for _ in range(num_patterns):
            p_day, p_col = _prev_cell_year(cur_day, cur_col)
            if p_day < 0 or p_col is None: pat = ''
            else:
                pat = df.iloc[p_day][p_col]
                pattern_months.add(p_col)
            patterns.append(pat[-2:] if isinstance(pat, str) and len(pat) >= 2 else '')
            cur_day, cur_col = (p_day, p_col)
    else:
        year_col = df.columns[-1]
        for offset in range(1, num_patterns + 1):
            idx = row_idx - offset
            pat = df.iloc[idx][year_col] if idx >= 0 else ''
            patterns.append(pat[-2:] if isinstance(pat, str) and len(pat) >= 2 else '')
    patterns.reverse()
    
    def matches_last_two_digits(v, p): return isinstance(v, str) and len(v) >= 2 and v[-2:] == p
    def contains_two_digits(v, p):
        if not (isinstance(v, str) and len(v) >= 2 and isinstance(p, str) and len(p) == 2): return False
        return p[0] in v and p[1] in v
    match_func = matches_last_two_digits if exact_match else contains_two_digits
    
    all_results, cau_positions, predict_positions, dan_so_sets = [], set(), set(), [[] for _ in range(12)]
    cols_full = list(df.columns)
    cols_to_scan = [c for c in cols_full if c not in ['Ngày'] and (c.isdigit() or c.startswith('TH'))]
    if is_year_data:
        cols_to_scan = [c for c in cols_to_scan if c not in pattern_months and c != selected_month_col]
    else:
        current_year_col = df.columns[-1]
        cols_to_scan = [c for c in cols_to_scan if c != current_year_col]
        
    steps_to_iterate = range(6) if step_to_run is None else [int(step_to_run)]
    
    for step in steps_to_iterate:
        for dir_idx, inside in enumerate([True, False]):
            direction_label = "Từ trên xuống" if inside else "Từ dưới lên"
            gap, count, result_nums = step + 1, 0, []
            for col_name in cols_to_scan:
                for i in range(len(df)):
                    if (inside and (i + (num_patterns - 1) * gap) >= len(df)) or \
                       (not inside and (i - (num_patterns - 1) * gap) < 0): continue
                    ok, pos = True, []
                    for k in range(num_patterns):
                        row_offset = k * gap if inside else -k * gap
                        v = df.iloc[i + row_offset][col_name]
                        if not match_func(v, patterns[k]):
                            ok = False
                            break
                        pos.append({'row': i + row_offset, 'col': cols_full.index(col_name)})
                    if ok:
                        predict_idx = i + (num_patterns * gap if inside else -num_patterns * gap)
                        if 0 <= predict_idx < len(df):
                            count += 1
                            cau_positions.update(json.dumps(p) for p in pos)
                            pv = df.iloc[predict_idx][col_name]
                            if pv:
                                result_nums.append(pv)
                                predict_positions.add(json.dumps({'row': predict_idx, 'col': cols_full.index(col_name)}))
            idx = dir_idx * 6 + step
            dan_so_sets[idx] = [[a + b for a in num for b in num] for num in result_nums]
            result_text = f"<b>{direction_label} – Cách {step}:</b> {count} cầu"
            if result_nums: result_text += f"<br><i>Giá trị:</i> {','.join(result_nums)}"
            else: result_text += "<br><i>Giá trị:</i> Không tìm thấy cầu"
            all_results.append(result_text)

    return jsonify({
        'success': True, 'patterns': patterns, 'stats_html': '<hr>'.join(all_results),
        'cau_positions': [json.loads(p) for p in cau_positions],
        'predict_positions': [json.loads(p) for p in predict_positions],
        'dan_so_sets': dan_so_sets
    })

# KHỐI GÂY LỖI ĐÃ ĐƯỢC XÓA BỎ
