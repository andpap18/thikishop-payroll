import streamlit as st
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import re
import io
import tempfile
import os

# --- Configuration ---
FILL_HEADER_GREY = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
FILL_ORANGE = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
FILL_LIGHT_ORANGE = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
BORDER_THIN = Side(style='thin', color="000000")
BORDER_THICK = Side(style='medium', color="000000")
BORDER_ALL_THIN = Border(left=BORDER_THIN, right=BORDER_THIN, top=BORDER_THIN, bottom=BORDER_THIN)

# Location colors (from schedule_transformer)
FILL_RENTIS = PatternFill(start_color="FCE4D6", fill_type="solid")
FILL_AIGALEO = PatternFill(start_color="E2EFDA", fill_type="solid") 
FILL_PEIRAIAS = PatternFill(start_color="DDEBF7", fill_type="solid")
FILL_PERISTERI = PatternFill(start_color="F4B084", fill_type="solid")

def clean_name(name):
    """Removes suffixes like (8ΩΡΟΣ), (4ΩΡΟΣ) and extra spaces."""
    if not name: return ""
    name = str(name).split('(')[0]
    return name.strip()

def parse_hours(time_str):
    """Parses '09:00-17:00' to decimal hours (e.g., 8.0). Returns 0 if invalid or off."""
    if not time_str or not isinstance(time_str, str):
        return 0.0
    
    time_str = re.sub(r'\[.*?\]', '', time_str).strip()
    
    # Special case: "Α" (leave/vacation) counts as 8 hours
    if time_str.upper() == 'Α' or time_str.upper() == 'A':
        return 8.0
    
    if '-' not in time_str:
        return 0.0
    
    try:
        start_str, end_str = time_str.split('-')
        start_parts = start_str.strip().split(':')
        end_parts = end_str.strip().split(':')
        
        start_h = int(start_parts[0]) + int(start_parts[1])/60
        end_h = int(end_parts[0]) + int(end_parts[1])/60
        
        diff = end_h - start_h
        if diff < 0: diff += 24
        return diff
    except:
        return 0.0

def has_work_content(val_str):
    """Check if cell contains actual work (not RR, ΡΕΠΟ, etc)"""
    if not val_str: return False
    val_str = str(val_str).strip().upper()
    if val_str in ["NONE", "", "RR", "ΡΕΠΟ", "ΑΝΑΡΡΩΤΙΚΗ"]: return False
    return True

def get_file_date_score(filename):
    """Parses filename for sorting."""
    months = {
        'ΙΑΝ': 1, 'ΦΕΒ': 2, 'ΜΑΡ': 3, 'ΑΠΡ': 4, 'ΜΑΙ': 5, 'ΙΟΥΝ': 6,
        'ΙΟΥΛ': 7, 'ΑΥΓ': 8, 'ΣΕΠ': 9, 'ΟΚΤ': 10, 'ΝΟΕ': 11, 'ΔΕΚ': 12
    }
    
    upper_name = filename.upper()
    match = re.search(r'(\d+)_([Α-Ω]+)', upper_name)
    if match:
        day = int(match.group(1))
        month_str = match.group(2)
        
        month_num = 0
        for m_name, m_val in months.items():
            if m_name in month_str:
                month_num = m_val
                break
        
        if month_num > 0:
            return month_num * 100 + day
            
    match_num = re.search(r'(\d+)', filename)
    if match_num:
        return int(match_num.group(1))
        
    return 99999

def process_payroll(uploaded_files, target_month):
    """Main payroll processing function."""
    
    # Greek Month Map for Date Parsing
    greek_months = {
        'ΙΑΝΟΥΑΡΙΟΥ': 1, 'ΦΕΒΡΟΥΑΡΙΟΥ': 2, 'ΜΑΡΤΙΟΥ': 3, 'ΑΠΡΙΛΙΟΥ': 4, 'ΜΑΙΟΥ': 5, 'ΜΑΪΟΥ': 5,
        'ΙΟΥΝΙΟΥ': 6, 'ΙΟΥΛΙΟΥ': 7, 'ΑΥΓΟΥΣΤΟΥ': 8, 'ΣΕΠΤΕΜΒΡΙΟυ': 9, 'ΟΚΤΩΒΡΙΟΥ': 10, 'ΝΟΕΜΒΡΙΟΥ': 11, 'ΔΕΚΕΜΒΡΙΟΥ': 12
    }
    
    # Month names for filename
    month_names = {
        1: 'ΙΑΝΟΥΑΡΙΟΣ', 2: 'ΦΕΒΡΟΥΑΡΙΟΣ', 3: 'ΜΑΡΤΙΟΣ', 4: 'ΑΠΡΙΛΙΟΣ', 
        5: 'ΜΑΙΟΣ', 6: 'ΙΟΥΝΙΟΣ', 7: 'ΙΟΥΛΙΟΣ', 8: 'ΑΥΓΟΥΣΤΟΣ',
        9: 'ΣΕΠΤΕΜΒΡΙΟΣ', 10: 'ΟΚΤΩΒΡΙΟΣ', 11: 'ΝΟΕΜΒΡΙΟΣ', 12: 'ΔΕΚΕΜΒΡΙΟΣ'
    }
    
    # Sort files
    file_list = [(f.name, f) for f in uploaded_files]
    file_list.sort(key=lambda x: get_file_date_score(x[0]))
    
    # Create output workbook
    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = "ΜΙΣΘΟΔΟΣΙΑ"
    
    current_row = 1
    monthly_stats = {}
    
    # Process each file
    for file_name, file_obj in file_list:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(file_obj.getvalue())
            tmp_path = tmp.name
        
        try:
            wb_in = openpyxl.load_workbook(tmp_path)
            ws_in = wb_in.active
            
            # Date filtering logic
            last_data_col = 26
            include_col_map = {}
            
            col_ptr = 2
            dates_found = False
            
            for i in range(7):
                is_sunday = (i == 6)
                span = 1 if is_sunday else 4
                
                date_cell = ws_in.cell(row=2, column=col_ptr)
                date_val_raw = date_cell.value
                
                include_day = True
                if target_month and date_val_raw:
                    parsed_month = None
                    
                    if hasattr(date_val_raw, 'month'):
                        parsed_month = date_val_raw.month
                        dates_found = True
                    else:
                        date_val = str(date_val_raw).strip().upper()
                        
                        if '/' in date_val:
                            try:
                                parts = date_val.split('/')
                                if len(parts) >= 2:
                                    parsed_month = int(parts[1])
                                    dates_found = True
                            except: pass
                        
                        elif any(m in date_val for m in greek_months.keys()):
                            for m_name, m_val in greek_months.items():
                                if m_name in date_val:
                                    parsed_month = m_val
                                    dates_found = True
                                    break
                    
                    if parsed_month:
                        if parsed_month != target_month:
                            include_day = False
                
                for k in range(span):
                    include_col_map[col_ptr + k] = include_day
                
                col_ptr += span
            
            if not dates_found and target_month:
                for col_idx in include_col_map.keys():
                    include_col_map[col_idx] = True
            
            # Write Week Title
            ws_out.cell(row=current_row, column=1).value = file_name.replace("(ΕΠΙΘ).xlsx", "").replace(".xlsx", "")
            ws_out.cell(row=current_row, column=1).font = Font(bold=True, size=12)
            current_row += 1
            
            # Copy Headers (Rows 1-3)
            for r in range(1, 4):
                for c in range(1, last_data_col + 1):
                    cell_in = ws_in.cell(row=r, column=c)
                    cell_out = ws_out.cell(row=current_row + r - 1, column=c)
                    cell_out.value = cell_in.value
                    
                    if cell_in.has_style:
                        cell_out.font = Font(name=cell_in.font.name, size=cell_in.font.size, bold=True)
                        cell_out.alignment = Alignment(horizontal=cell_in.alignment.horizontal, vertical=cell_in.alignment.vertical, wrap_text=cell_in.alignment.wrap_text)
                        cell_out.border = BORDER_ALL_THIN
                        if cell_in.fill and cell_in.fill.start_color.index != '00000000':
                             cell_out.fill = PatternFill(start_color=cell_in.fill.start_color.index, fill_type='solid')
                    
                    if c in include_col_map and not include_col_map[c]:
                        cell_out.fill = PatternFill(start_color="EEEEEE", fill_type="solid")
                    
                    ws_out.column_dimensions[get_column_letter(c)].width = 16
            
            # Re-apply merges
            base_r = current_row
            col_ptr = 2
            for i in range(7):
                is_sunday = (i == 6)
                span = 1 if is_sunday else 4
                ws_out.merge_cells(start_row=base_r, start_column=col_ptr, end_row=base_r, end_column=col_ptr+span-1)
                ws_out.merge_cells(start_row=base_r+1, start_column=col_ptr, end_row=base_r+1, end_column=col_ptr+span-1)
                col_ptr += span
            
            # Add Calculation Headers
            calc_headers = ["ΗΜΕΡΕΣ ΕΡΓΑΣΙΑΣ", "ΩΡΕΣ/ΕΒΔΟ", "ΥΠΕΡΕΡΓΑΣΙΑ (h)", "ΥΠΕΡΩΡΙΕΣ(h)"]
            calc_col_start = last_data_col + 1
            
            for i, header in enumerate(calc_headers):
                c = ws_out.cell(row=current_row + 2, column=calc_col_start + i)
                c.value = header
                c.font = Font(bold=True, size=9)
                c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                c.border = BORDER_ALL_THIN
                if i == 0: c.fill = PatternFill(start_color="FFFFFF", fill_type="solid")
                elif i == 1: c.fill = PatternFill(start_color="FFFFFF", fill_type="solid")
                elif i == 2: c.fill = FILL_ORANGE
                elif i == 3: c.fill = FILL_LIGHT_ORANGE
                ws_out.column_dimensions[get_column_letter(calc_col_start + i)].width = 14
            
            current_row += 3
            
            # Process Data Rows
            row_in = 4
            while True:
                name_cell = ws_in.cell(row=row_in, column=1)
                raw_name = name_cell.value
                if not raw_name:
                    break
                
                clean_n = clean_name(raw_name)
                if clean_n not in monthly_stats:
                    monthly_stats[clean_n] = {'overwork': 0, 'overtime': 0, 'sundays': 0, 'days_worked': 0}
                
                c_name = ws_out.cell(row=current_row, column=1)
                c_name.value = clean_n
                c_name.font = Font(bold=True)
                c_name.border = BORDER_ALL_THIN
                
                total_hours = 0.0
                sunday_worked = False
                days_worked = 0
                
                col_ptr = 2
                
                for day_idx in range(7):
                    is_sunday = (day_idx == 6)
                    span = 1 if is_sunday else 4
                    
                    day_hours = 0.0
                    is_included = include_col_map.get(col_ptr, True)
                    
                    for k in range(span):
                        c_in = ws_in.cell(row=row_in, column=col_ptr + k)
                        c_out = ws_out.cell(row=current_row, column=col_ptr + k)
                        
                        if is_included:
                            c_out.value = c_in.value
                            if c_in.fill: c_out.fill = PatternFill(start_color=c_in.fill.start_color.index, fill_type='solid')
                            
                            val = str(c_in.value).strip() if c_in.value else ""
                            if val and val not in ["None", "RR", "ΡΕΠΟ", "ΑΝΑΡΡΩΤΙΚΗ", "ΑΔΕΙΑ"]:
                                 h = parse_hours(val)
                                 if h > 0: day_hours += h
                        else:
                            c_out.value = ""
                            c_out.fill = PatternFill(start_color="EEEEEE", fill_type="solid")
                        
                        c_out.border = BORDER_ALL_THIN
                        c_out.alignment = Alignment(horizontal='center', vertical='center')
                        c_out.font = Font(bold=True)
                    
                    total_hours += day_hours
                    if is_sunday and day_hours > 0:
                        sunday_worked = True
                    
                    if day_hours > 0:
                        days_worked += 1
                    
                    col_ptr += span
                
                # Threshold is ALWAYS 40 hours (5-day work week standard)
                # This applies regardless of how many days were actually worked
                weekly_threshold = 40
                
                overwork = 0
                overtime = 0
                
                if total_hours > weekly_threshold:
                    remainder = total_hours - weekly_threshold
                    overwork = min(remainder, 5)
                    if remainder > 5:
                        overtime = remainder - 5
                
                monthly_stats[clean_n]['overwork'] += overwork
                monthly_stats[clean_n]['overtime'] += overtime
                monthly_stats[clean_n]['days_worked'] += days_worked
                if sunday_worked:
                    monthly_stats[clean_n]['sundays'] += 1
                
                # Write Calculated Columns
                c_days = ws_out.cell(row=current_row, column=calc_col_start)
                c_days.value = days_worked
                c_days.alignment = Alignment(horizontal='center')
                c_days.border = BORDER_ALL_THIN
                c_days.font = Font(bold=True)
                
                c_total = ws_out.cell(row=current_row, column=calc_col_start + 1)
                c_total.value = total_hours
                c_total.alignment = Alignment(horizontal='center')
                c_total.border = BORDER_ALL_THIN
                c_total.font = Font(bold=True)
                if total_hours > 40: c_total.fill = FILL_ORANGE
                
                c_overwork = ws_out.cell(row=current_row, column=calc_col_start + 2)
                c_overwork.value = overwork
                c_overwork.alignment = Alignment(horizontal='center')
                c_overwork.border = BORDER_ALL_THIN
                c_overwork.font = Font(bold=True)
                if overwork > 0: c_overwork.fill = FILL_ORANGE
                
                c_overtime = ws_out.cell(row=current_row, column=calc_col_start + 3)
                c_overtime.value = overtime
                c_overtime.alignment = Alignment(horizontal='center')
                c_overtime.border = BORDER_ALL_THIN
                c_overtime.font = Font(bold=True)
                if overtime > 0: c_overtime.fill = FILL_LIGHT_ORANGE
                
                row_in += 1
                current_row += 1
            
            current_row += 2
            
        finally:
            os.unlink(tmp_path)
    
    # Generate Monthly Summary Table
    summary_headers = ["ΟΝΟΜΑΤΕΠΩΝΥΜΟ", "ΗΜΕΡΕΣ ΕΡΓΑΣΙΑΣ", "ΥΠΕΡΕΡΓΑΣΙΑ (h)", "ΥΠΕΡΩΡΙΕΣ(h)", "ΚΥΡΙΑΚΕΣ"]
    for i, header in enumerate(summary_headers):
        c = ws_out.cell(row=current_row, column=1 + i)
        c.value = header
        c.font = Font(bold=True)
        c.border = BORDER_THICK
        c.alignment = Alignment(horizontal='center')
        if i > 0: c.fill = FILL_HEADER_GREY
    
    current_row += 1
    
    for name, stats in monthly_stats.items():
        c = ws_out.cell(row=current_row, column=1)
        c.value = name
        c.border = BORDER_ALL_THIN
        c.fill = PatternFill(start_color="E7E6E6", fill_type="solid")
        c.font = Font(bold=True)
        
        c = ws_out.cell(row=current_row, column=2)
        c.value = stats['days_worked']
        c.alignment = Alignment(horizontal='center')
        c.border = BORDER_ALL_THIN
        c.font = Font(bold=True)
        
        c = ws_out.cell(row=current_row, column=3)
        c.value = stats['overwork']
        c.alignment = Alignment(horizontal='center')
        c.border = BORDER_ALL_THIN
        c.font = Font(bold=True)
        if stats['overwork'] > 0: c.fill = FILL_ORANGE
        
        c = ws_out.cell(row=current_row, column=4)
        c.value = stats['overtime']
        c.alignment = Alignment(horizontal='center')
        c.border = BORDER_ALL_THIN
        c.font = Font(bold=True)
        if stats['overtime'] > 0: c.fill = FILL_LIGHT_ORANGE
        
        c = ws_out.cell(row=current_row, column=5)
        c.value = stats['sundays']
        c.alignment = Alignment(horizontal='center')
        c.border = BORDER_ALL_THIN
        c.font = Font(bold=True)
        
        current_row += 1
    
    ws_out.column_dimensions['A'].width = 30
    
    # Save to bytes
    output = io.BytesIO()
    wb_out.save(output)
    output.seek(0)
    
    # Generate filename
    if target_month in month_names:
        filename = f"ΣΥΓΚΕΝΤΡΩΤΙΚΟ_ΜΙΣΘΟΔΟΣΙΑΣ_{month_names[target_month]}.xlsx"
    else:
        filename = "ΣΥΓΚΕΝΤΡΩΤΙΚΟ_ΜΙΣΘΟΔΟΣΙΑΣ.xlsx"
    
    return output, filename, monthly_stats

def get_monthly_work_days(uploaded_files, target_month):
    """
    Scans uploaded files and calculates days worked for each employee.
    Returns a dictionary: {employee_name: days_worked}
    """
    greek_months = {
        'ΙΑΝΟΥΑΡΙΟΥ': 1, 'ΦΕΒΡΟΥΑΡΙΟΥ': 2, 'ΜΑΡΤΙΟΥ': 3, 'ΑΠΡΙΛΙΟΥ': 4, 'ΜΑΙΟΥ': 5, 'ΜΑΪΟΥ': 5,
        'ΙΟΥΝΙΟΥ': 6, 'ΙΟΥΛΙΟΥ': 7, 'ΑΥΓΟΥΣΤΟΥ': 8, 'ΣΕΠΤΕΜΒΡΙΟΥ': 9, 'ΟΚΤΩΒΡΙΟΥ': 10, 'ΝΟΕΜΒΡΙΟΥ': 11, 'ΔΕΚΕΜΒΡΙΟΥ': 12
    }
    
    employee_days = {}
    
    for f in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(f.getvalue())
            tmp_path = tmp.name
            
        try:
            wb = openpyxl.load_workbook(tmp_path, data_only=True)
            ws = wb.active
            
            # Date filtering logic (same as payroll)
            include_col_map = {}
            col_ptr = 2
            dates_found = False
            
            for i in range(7):
                is_sunday = (i == 6)
                span = 1 if is_sunday else 4
                
                date_cell = ws.cell(row=2, column=col_ptr)
                date_val_raw = date_cell.value
                
                include_day = True
                if target_month and date_val_raw:
                    parsed_month = None
                    if hasattr(date_val_raw, 'month'):
                        parsed_month = date_val_raw.month
                        dates_found = True
                    else:
                        date_val = str(date_val_raw).strip().upper()
                        if '/' in date_val:
                            try:
                                parts = date_val.split('/')
                                if len(parts) >= 2:
                                    parsed_month = int(parts[1])
                                    dates_found = True
                            except: pass
                        elif any(m in date_val for m in greek_months.keys()):
                            for m_name, m_val in greek_months.items():
                                if m_name in date_val:
                                    parsed_month = m_val
                                    dates_found = True
                                    break
                    
                    if parsed_month and parsed_month != target_month:
                        include_day = False
                
                for k in range(span):
                    include_col_map[col_ptr + k] = include_day
                
                col_ptr += span
            
            if not dates_found and target_month:
                for col_idx in include_col_map.keys():
                    include_col_map[col_idx] = True
            
            # Scan rows for employees
            row_idx = 4
            while True:
                name_cell = ws.cell(row=row_idx, column=1)
                if not name_cell.value:
                    break
                
                clean_n = clean_name(str(name_cell.value))
                if clean_n not in employee_days:
                    employee_days[clean_n] = 0
                
                col_ptr = 2
                for day_idx in range(7):
                    is_sunday = (day_idx == 6)
                    span = 1 if is_sunday else 4
                    
                    day_hours = 0
                    is_included = include_col_map.get(col_ptr, True)
                    
                    for k in range(span):
                        if is_included:
                            c = ws.cell(row=row_idx, column=col_ptr + k)
                            val = str(c.value).strip() if c.value else ""
                            if val and val not in ["None", "RR", "ΡΕΠΟ", "ΑΝΑΡΡΩΤΙΚΗ", "ΑΔΕΙΑ"]:
                                h = parse_hours(val)
                                if h > 0: day_hours += h
                        
                    if day_hours > 0:
                        employee_days[clean_n] += 1
                        
                    col_ptr += span
                
                row_idx += 1
                
        except Exception:
            pass
        finally:
            try: os.unlink(tmp_path)
            except: pass
            
    return employee_days

def process_cost_analysis(uploaded_files, employee_costs, target_month):
    """Process weekly schedule files and create cost analysis by location."""
    
    # Greek Month Map for Date Parsing
    greek_months = {
        'ΙΑΝΟΥΑΡΙΟΥ': 1, 'ΦΕΒΡΟΥΑΡΙΟΥ': 2, 'ΜΑΡΤΙΟΥ': 3, 'ΑΠΡΙΛΙΟΥ': 4, 'ΜΑΙΟΥ': 5, 'ΜΑΪΟΥ': 5,
        'ΙΟΥΝΙΟΥ': 6, 'ΙΟΥΛΙΟΥ': 7, 'ΑΥΓΟΥΣΤΟΥ': 8, 'ΣΕΠΤΕΜΒΡΙΟΥ': 9, 'ΟΚΤΩΒΡΙΟΥ': 10, 'ΝΟΕΜΒΡΙΟΥ': 11, 'ΔΕΚΕΜΒΡΙΟΥ': 12
    }
    
    # Sort files
    file_list = [(f.name, f) for f in uploaded_files]
    file_list.sort(key=lambda x: get_file_date_score(x[0]))
    
    # Create output workbook
    wb_out = openpyxl.Workbook()
    ws_out = wb_out.active
    ws_out.title = "ΚΟΣΤΟΛΟΓΗΣΗ"
    
    current_row = 1
    location_costs = {"ΡΕΝΤΗΣ": 0, "ΑΙΓΑΛΕΩ": 0, "ΠΕΙΡΑΙΑΣ": 0, "ΠΕΡΙΣΤΕΡΙ": 0}
    
    # DEBUG: Track color detections
    debug_colors = []
    
    # Process each file
    for file_name, file_obj in file_list:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(file_obj.getvalue())
            tmp_path = tmp.name
        
        try:
            wb_in = openpyxl.load_workbook(tmp_path)
            ws_in = wb_in.active
            
            # Date filtering logic (same as payroll)
            last_data_col = 26
            include_col_map = {}
            
            col_ptr = 2
            dates_found = False
            
            for i in range(7):
                is_sunday = (i == 6)
                span = 1 if is_sunday else 4
                
                date_cell = ws_in.cell(row=2, column=col_ptr)
                date_val_raw = date_cell.value
                
                include_day = True
                if target_month and date_val_raw:
                    parsed_month = None
                    
                    if hasattr(date_val_raw, 'month'):
                        parsed_month = date_val_raw.month
                        dates_found = True
                    else:
                        date_val = str(date_val_raw).strip().upper()
                        
                        if '/' in date_val:
                            try:
                                parts = date_val.split('/')
                                if len(parts) >= 2:
                                    parsed_month = int(parts[1])
                                    dates_found = True
                            except: pass
                        
                        elif any(m in date_val for m in greek_months.keys()):
                            for m_name, m_val in greek_months.items():
                                if m_name in date_val:
                                    parsed_month = m_val
                                    dates_found = True
                                    break
                    
                    if parsed_month:
                        if parsed_month != target_month:
                            include_day = False
                
                for k in range(span):
                    include_col_map[col_ptr + k] = include_day
                
                col_ptr += span
            
            if not dates_found and target_month:
                for col_idx in include_col_map.keys():
                    include_col_map[col_idx] = True
            
            # Write Week Title
            ws_out.cell(row=current_row, column=1).value = file_name.replace("(ΕΠΙΘ).xlsx", "").replace(".xlsx", "")
            ws_out.cell(row=current_row, column=1).font = Font(bold=True, size=12)
            current_row += 1
            
            # Copy Headers (Rows 1-3)
            for r in range(1, 4):
                for c in range(1, last_data_col + 1):
                    cell_in = ws_in.cell(row=r, column=c)
                    cell_out = ws_out.cell(row=current_row + r - 1, column=c)
                    cell_out.value = cell_in.value
                    
                    if cell_in.has_style:
                        cell_out.font = Font(name=cell_in.font.name, size=cell_in.font.size, bold=True)
                        cell_out.alignment = Alignment(horizontal=cell_in.alignment.horizontal, vertical=cell_in.alignment.vertical, wrap_text=cell_in.alignment.wrap_text)
                        cell_out.border = BORDER_ALL_THIN
                        if cell_in.fill and cell_in.fill.start_color.index != '00000000':
                             cell_out.fill = PatternFill(start_color=cell_in.fill.start_color.index, fill_type='solid')
                    
                    if c in include_col_map and not include_col_map[c]:
                        cell_out.fill = PatternFill(start_color="EEEEEE", fill_type="solid")
                    
                    ws_out.column_dimensions[get_column_letter(c)].width = 16
            
            # Re-apply merges
            base_r = current_row
            col_ptr = 2
            for i in range(7):
                is_sunday = (i == 6)
                span = 1 if is_sunday else 4
                ws_out.merge_cells(start_row=base_r, start_column=col_ptr, end_row=base_r, end_column=col_ptr+span-1)
                ws_out.merge_cells(start_row=base_r+1, start_column=col_ptr, end_row=base_r+1, end_column=col_ptr+span-1)
                col_ptr += span
            
            current_row += 3
            
            # Process Data Rows - REPLACE HOURS WITH COSTS
            row_in = 4
            while True:
                name_cell = ws_in.cell(row=row_in, column=1)
                raw_name = name_cell.value
                if not raw_name:
                    break
                
                clean_n = clean_name(raw_name)
                
                # Write employee name
                c_name = ws_out.cell(row=current_row, column=1)
                c_name.value = clean_n
                c_name.font = Font(bold=True)
                c_name.border = BORDER_ALL_THIN
                
                col_ptr = 2
                
                for day_idx in range(7):
                    is_sunday = (day_idx == 6)
                    span = 1 if is_sunday else 4
                    
                    is_included = include_col_map.get(col_ptr, True)
                    
                    for k in range(span):
                        c_in = ws_in.cell(row=row_in, column=col_ptr + k)
                        c_out = ws_out.cell(row=current_row, column=col_ptr + k)
                        
                        if is_included:
                            val = str(c_in.value).strip() if c_in.value else ""
                            
                            # Check if this is work (not RR, ΡΕΠΟ, etc)
                            is_work = False
                            if val and val not in ["None", "", "RR", "ΡΕΠΟ"]:
                                if "-" in val or val.upper() in ["Α", "A", "ΑΝΑΡΡΩΤΙΚΗ", "ΑΔΕΙΑ"]:
                                    is_work = True
                            
                            # Replace with cost if this is work
                            if is_work:
                                # Get daily cost (default to 0 if not in dict)
                                daily_cost = employee_costs.get(clean_n, 0.0)
                                c_out.value = daily_cost
                                c_out.number_format = '0.00'
                                
                                # Track location cost based on COLUMN POSITION (more reliable than color)
                                if daily_cost > 0:
                                    location = None
                                    
                                    # Determine location based on column index (k)
                                    if span == 4:
                                        if k == 0: location = "ΡΕΝΤΗΣ"
                                        elif k == 1: location = "ΑΙΓΑΛΕΩ"
                                        elif k == 2: location = "ΠΕΙΡΑΙΑΣ"
                                        elif k == 3: location = "ΠΕΡΙΣΤΕΡΙ"
                                    elif span == 1:
                                        # Sunday usually has only 1 column. 
                                        # We can try to guess from header or default to RENTIS (most common)
                                        # Or check color as fallback
                                        location = "ΡΕΝΤΗΣ" # Default for Sunday
                                        
                                        # Optional: Check color just in case for Sunday
                                        if c_in.fill and hasattr(c_in.fill, 'start_color') and c_in.fill.start_color:
                                            try:
                                                color = c_in.fill.start_color.index
                                                color_clean = str(color).replace("00", "").upper()
                                                if "E2EFDA" in color_clean: location = "ΑΙΓΑΛΕΩ"
                                                elif "DDEBF7" in color_clean: location = "ΠΕΙΡΑΙΑΣ"
                                                elif "F4B084" in color_clean: location = "ΠΕΡΙΣΤΕΡΙ"
                                            except:
                                                pass
                                    
                                    if location:
                                        location_costs[location] += daily_cost
                                        
                                        # DEBUG: Track this
                                        debug_colors.append({
                                            'employee': clean_n,
                                            'cost': daily_cost,
                                            'location': location,
                                            'method': f"Column {k} (Span {span})"
                                        })
                            else:
                                # Keep original value
                                c_out.value = c_in.value
                            
                            # Copy styling
                            if c_in.fill: 
                                try:
                                    c_out.fill = PatternFill(start_color=c_in.fill.start_color.index, fill_type='solid')
                                except:
                                    pass
                        else:
                            c_out.value = ""
                            c_out.fill = PatternFill(start_color="EEEEEE", fill_type="solid")
                        
                        c_out.border = BORDER_ALL_THIN
                        c_out.alignment = Alignment(horizontal='center', vertical='center')
                        c_out.font = Font(bold=True)
                    
                    col_ptr += span
                
                row_in += 1
                current_row += 1
            
            current_row += 2
            
        finally:
            os.unlink(tmp_path)
    
    # Add ΚΟΣΤΟΣ ΑΝΑ ΚΑΤΑΣΤΗΜΑ summary
    summary_row = current_row + 1
    
    # Create fresh header cells
    for c in range(1, 5):
        cell = ws_out.cell(row=summary_row, column=c)
        cell.value = None
        cell.border = Border()
        cell.fill = PatternFill()
    
    # Merge first
    ws_out.merge_cells(start_row=summary_row, start_column=1, end_row=summary_row, end_column=4)
    
    # Then style the merged cell
    header_cell = ws_out.cell(row=summary_row, column=1)
    header_cell.value = "ΚΟΣΤΟΣ ΑΝΑ ΚΑΤΑΣΤΗΜΑ"
    header_cell.font = Font(bold=True, size=14)
    header_cell.border = Border(
        left=BORDER_THICK,
        right=BORDER_THICK,
        top=BORDER_THICK,
        bottom=BORDER_THICK
    )
    
    summary_row += 1
    
    # Data rows
    for location, cost in location_costs.items():
        # Location name
        cell_name = ws_out.cell(row=summary_row, column=1)
        cell_name.value = location
        cell_name.font = Font(bold=True)
        cell_name.border = BORDER_ALL_THIN
        cell_name.fill = FILL_HEADER_GREY
        
        # Cost value
        cell_cost = ws_out.cell(row=summary_row, column=2)
        cell_cost.value = cost
        cell_cost.number_format = '#,##0.00'
        cell_cost.font = Font(bold=True)
        cell_cost.border = BORDER_ALL_THIN
        cell_cost.alignment = Alignment(horizontal='right')
        
        summary_row += 1
    
    ws_out.column_dimensions['A'].width = 30
    
    # Save to bytes
    output = io.BytesIO()
    wb_out.save(output)
    output.seek(0)
    
    return output, location_costs, debug_colors

# === STREAMLIT UI ===
st.set_page_config(page_title="ThikiShop Μισθοδοσία & Κοστολόγηση", page_icon="📊", layout="wide")

st.title("📊 ThikiShop - Μισθοδοσία & Κοστολόγηση")
st.markdown("---")

# Create tabs
tab1, tab2 = st.tabs(["💰 Μισθοδοσία", "🏪 Κοστολόγηση Καταστημάτων"])

# === TAB 1: PAYROLL ===
with tab1:
    st.header("Αυτόματη Δημιουργία Μισθοδοσίας")
    
    with st.expander("📖 Οδηγίες Χρήσης"):
        st.markdown("""
        ### Πώς να χρησιμοποιήσεις:
        
        1. **Upload**: Ανέβασε τα εβδομαδιαία αρχεία `(ΕΠΙΘ).xlsx`
        2. **Επιλογή Μήνα**: Διάλεξε τον μήνα
        3. **Δημιουργία**: Πάτα "Δημιουργία Μισθοδοσίας"
        4. **Download**: Κατέβασε το αρχείο
        
        ### Τι υπολογίζει:
        - **Ημέρες Εργασίας**: Πόσες μέρες δούλεψε (εκτός RR/ΡΕΠΟ)
        - **Ώρες/Εβδομάδα**: Συνολικές ώρες
        - **Υπερεργασία**: Ώρες πάνω από (Ημέρες × 8), μέχρι +5h
        - **Υπερωρίες**: Ώρες πάνω από (Ημέρες × 8) + 5h
        - **"Α"** (Άδεια) μετράει ως 8 ώρες και 1 μέρα εργασίας
        """)
    
    st.subheader("1️⃣ Ανέβασε τα Εβδομαδιαία Προγράμματα")
    uploaded_files = st.file_uploader(
        "Επίλεξε αρχεία Excel (ΕΠΙΘ).xlsx",
        type=['xlsx'],
        accept_multiple_files=True,
        help="Μπορείς να επιλέξεις πολλά αρχεία ταυτόχρονα",
        key="payroll_upload"
    )
    
    if uploaded_files:
        st.success(f"✅ Ανέβηκαν {len(uploaded_files)} αρχεία")
        with st.expander("Προβολή αρχείων"):
            for f in uploaded_files:
                st.write(f"- {f.name}")
    
    st.subheader("2️⃣ Επιλογή Μήνα")
    month_names_display = {
        1: 'Ιανουάριος', 2: 'Φεβρουάριος', 3: 'Μάρτιος', 4: 'Απρίλιος',
        5: 'Μάιος', 6: 'Ιούνιος', 7: 'Ιούλιος', 8: 'Αύγουστος',
        9: 'Σεπτέμβριος', 10: 'Οκτώβριος', 11: 'Νοέμβριος', 12: 'Δεκέμβριος'
    }
    
    selected_month = st.selectbox(
        "Διάλεξε μήνα:",
        options=list(month_names_display.keys()),
        format_func=lambda x: month_names_display[x],
        index=10,
        key="payroll_month"
    )
    
    st.subheader("3️⃣ Δημιουργία Μισθοδοσίας")
    
    if st.button("🚀 Δημιουργία Μισθοδοσίας", type="primary", use_container_width=True, key="gen_payroll"):
        if not uploaded_files:
            st.error("❌ Παρακαλώ ανέβασε τουλάχιστον ένα αρχείο!")
        else:
            with st.spinner(f"Επεξεργασία {len(uploaded_files)} αρχείων..."):
                try:
                    output_file, filename, monthly_stats = process_payroll(uploaded_files, selected_month)
                    
                    st.success(f"✅ Επιτυχής δημιουργία του {filename}")
                    
                    # Store in session state for Tab 2
                    st.session_state['payroll_file'] = output_file
                    st.session_state['payroll_filename'] = filename
                    st.session_state['monthly_stats'] = monthly_stats
                    
                    # Download Button
                    st.download_button(
                        label="📥 Κατέβασε το Αρχείο Μισθοδοσίας",
                        data=output_file,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                    st.info("💡 Τώρα μπορείς να πας στο Tab 'Κοστολόγηση Καταστημάτων' για να δεις το κόστος ανά κατάστημα!")
                    
                except Exception as e:
                    st.error(f"❌ Σφάλμα κατά την επεξεργασία: {str(e)}")
                    st.exception(e)

# === TAB 2: COST ANALYSIS ===
with tab2:
    st.header("Κοστολόγηση Ανά Κατάστημα")
    
    with st.expander("📖 Οδηγίες Χρήσης"):
        st.markdown("""
        ### Πώς να χρησιμοποιήσεις:
        
        1. **Upload**: Ανέβασε τα εβδομαδιαία αρχεία `(ΕΠΙΘ).xlsx`
        2. **Επιλογή Μήνα**: Διάλεξε τον μήνα
        3. **Καταχώρηση Κόστους**: Συμπλήρωσε το μηνιαίο κόστος για κάθε εργαζόμενο
        4. **Υπολογισμός**: Πάτα "Δημιουργία Κοστολόγησης"
        5. **Download**: Κατέβασε το αρχείο με τα κόστη
        
        ### Τι υπολογίζει:
        - Ημερήσιο κόστος = Μηνιαίο κόστος ÷ Ημέρες εργασίας
        - Αντικαθιστά ωράρια/Α/ΑΝΑΡΡΩΤΙΚΗ με ημερήσιο κόστος
        - Υπολογίζει συνολικό κόστος ανά κατάστημα (ΡΕΝΤΗΣ, ΑΙΓΑΛΕΩ, ΠΕΙΡΑΙΑΣ, ΠΕΡΙΣΤΕΡΙ)
        """)
    
    st.subheader("1️⃣ Ανέβασε τα Εβδομαδιαία Προγράμματα")
    
    # Check if we can reuse from Tab 1
    if 'monthly_stats' in st.session_state:
        st.info("💡 Μπορείς να χρησιμοποιήσεις τα ίδια αρχεία από το Tab Μισθοδοσία ή να ανεβάσεις νέα!")
        monthly_stats = st.session_state['monthly_stats']
    else:
        monthly_stats = None
    
    cost_uploaded_files = st.file_uploader(
        "Επίλεξε αρχεία Excel (ΕΠΙΘ).xlsx",
        type=['xlsx'],
        accept_multiple_files=True,
        help="Μπορείς να επιλέξεις πολλά αρχεία ταυτόχρονα",
        key="cost_upload"
    )
    
    if cost_uploaded_files:
        st.success(f"✅ Ανέβηκαν {len(cost_uploaded_files)} αρχεία")
        with st.expander("Προβολή αρχείων"):
            for f in cost_uploaded_files:
                st.write(f"- {f.name}")
    
    st.subheader("2️⃣ Επιλογή Μήνα")
    cost_selected_month = st.selectbox(
        "Διάλεξε μήνα:",
        options=list(month_names_display.keys()),
        format_func=lambda x: month_names_display[x],
        index=10,
        key="cost_month"
    )
    
    # Get employee list and work days from uploaded files
    if cost_uploaded_files:
        # Calculate work days dynamically from the uploaded files
        with st.spinner("🔄 Υπολογισμός ημερών εργασίας από τα αρχεία..."):
            current_work_days = get_monthly_work_days(cost_uploaded_files, cost_selected_month)
        
        if current_work_days:
            employee_list = sorted(list(current_work_days.keys()))
            st.success(f"✅ Βρέθηκαν {len(employee_list)} εργαζόμενοι και υπολογίστηκαν οι ημέρες εργασίας τους!")
        else:
            st.warning("⚠️ Δεν βρέθηκαν εργαζόμενοι στα αρχεία.")
            employee_list = []

        if employee_list:
            st.subheader("3️⃣ Καταχώρηση Μηνιαίου Κόστους")
            
            st.markdown("Συμπλήρωσε το **μηνιαίο κόστος** για κάθε εργαζόμενο:")
            
            employee_costs = {}
            
            # Create form for employee costs
            cols = st.columns(2)
            for idx, employee_name in enumerate(employee_list):
                col = cols[idx % 2]
                
                with col:
                    # Get days worked
                    days = current_work_days.get(employee_name, 0)
                    days_info = f" ({days} ημέρες)"
                    
                    monthly_cost = st.number_input(
                        f"{employee_name}{days_info}",
                        min_value=0.0,
                        step=0.01,
                        format="%.2f",
                        key=f"cost_{employee_name}"
                    )
                    
                    if monthly_cost > 0:
                        # Calculate daily cost
                        if days > 0:
                            daily_cost = monthly_cost / days
                            employee_costs[employee_name] = daily_cost
                            st.caption(f"→ Ημερήσιο: {daily_cost:.2f}€ (÷{days})")
                        else:
                            st.warning(f"⚠️ Δεν δούλεψε καμία μέρα (Διαίρεση με 0)!")
                            employee_costs[employee_name] = 0.0
            
            st.subheader("4️⃣ Δημιουργία Κοστολόγησης")
            
            if st.button("🚀 Δημιουργία Κοστολόγησης", type="primary", use_container_width=True, key="gen_cost"):
                if not employee_costs:
                    st.error("❌ Παρακαλώ συμπλήρωσε κόστη για τουλάχιστον έναν εργαζόμενο!")
                else:
                    with st.spinner("Υπολογισμός κόστους ανά κατάστημα..."):
                        try:
                            # Show debug info
                            st.info(f"📊 Επεξεργασία {len(employee_costs)} εργαζομένων με κόστη")
                            
                            # Debug: show employee_costs
                            with st.expander("🔍 Debug: Εργαζόμενοι με Κόστη"):
                                for emp, cost in employee_costs.items():
                                    st.write(f"- {emp}: {cost:.2f}€/μέρα")
                            
                            cost_file, location_costs, debug_colors = process_cost_analysis(cost_uploaded_files, employee_costs, cost_selected_month)
                            
                            st.success("✅ Επιτυχής δημιουργία κοστολόγησης!")
                            
                            # DEBUG: Show color detections
                            if debug_colors:
                                with st.expander("🔍 Debug: Ανίχνευση Τοποθεσίας"):
                                    st.write(f"Βρέθηκαν {len(debug_colors)} εγγραφές:")
                                    for item in debug_colors[:20]:  # Show first 20
                                        st.write(f"- {item['employee']}: {item['cost']:.2f}€ | Μέθοδος: {item.get('method', 'N/A')} | Κατάστημα: {item['location']}")
                            
                            # Show summary
                            st.subheader("📊 Κόστος Ανά Κατάστημα")
                            
                            total_cost = sum(location_costs.values())
                            
                            if total_cost == 0:
                                st.warning("⚠️ Το συνολικό κόστος είναι 0! Ελέγξτε αν τα ονόματα ταιριάζουν ακριβώς με τα αρχεία.")
                            
                            summary_data = {
                                "Κατάστημα": list(location_costs.keys()),
                                "Κόστος (€)": [f"{cost:.2f}" for cost in location_costs.values()]
                            }
                            
                            st.table(summary_data)
                            
                            # Download button
                            month_names = {
                                1: 'ΙΑΝΟΥΑΡΙΟΣ', 2: 'ΦΕΒΡΟΥΑΡΙΟΣ', 3: 'ΜΑΡΤΙΟΣ', 4: 'ΑΠΡΙΛΙΟΣ',
                                5: 'ΜΑΙΟΣ', 6: 'ΙΟΥΝΙΟΣ', 7: 'ΙΟΥΛΙΟΣ', 8: 'ΑΥΓΟΥΣΤΟΣ',
                                9: 'ΣΕΠΤΕΜΒΡΙΟΣ', 10: 'ΟΚΤΩΒΡΙΟΣ', 11: 'ΝΟΕΜΒΡΙΟΣ', 12: 'ΔΕΚΕΜΒΡΙΟΣ'
                            }
                            filename = f"ΚΟΣΤΟΛΟΓΗΣΗ_ΚΑΤΑΣΤΗΜΑΤΑ_{month_names.get(cost_selected_month, 'OUTPUT')}.xlsx"
                            
                            st.download_button(
                                label="📥 Κατέβασε την Κοστολόγηση",
                                data=cost_file,
                                file_name=filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                            
                        except Exception as e:
                            st.error(f"❌ Σφάλμα: {str(e)}")
                            st.exception(e)

# Footer
st.markdown("---")
st.markdown("*Developed for ThikiShop | Powered by Streamlit*")
