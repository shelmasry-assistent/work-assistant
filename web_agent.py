import os
import glob
import json
import datetime
import zipfile
import urllib.request
import xml.etree.ElementTree as ET
import streamlit as st
import pandas as pd
import oracledb
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "chat_history.json")
REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "reminders.json")
KNOWLEDGE_FOLDER = os.path.join(os.path.dirname(__file__), "knowledge_base")

ORACLE_HOST = os.getenv("ORACLE_HOST", "192.168.200.10")
ORACLE_PORT = os.getenv("ORACLE_PORT", "1521")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE", "XEPDB1")
ORACLE_USER = os.getenv("ORACLE_USER", "CONTRACTS_APP")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "imc#wis")
CONTRACTS_SERVER_URL = os.getenv("CONTRACTS_SERVER_URL", f"http://{ORACLE_HOST}:8099")

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    return [
        {"role": "assistant", "content": "أهلاً بك يا فندم! 👋 أنا مساعدك الذكي المربوط حياً وبشكل مباشر بقاعدة بيانات أوراكل (192.168.200.10) والمراسلات.\n\nكيف يمكنني دعمك اليوم؟ يمكنك طلب صياغة خطاب، مراجعة العقود المحدثة لحظياً، أو استعلامات أوراكل."}
    ]

def save_history(messages):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_reminders(reminders):
    try:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving reminders: {e}")

def sync_oracle_contracts_cache():
    """الاتصال المباشر والحي بقاعدة بيانات أوراكل 192.168.200.10 لضمان جلب البيانات المعدلة أولاً بأول دون أي بيانات ثنائية ثابتة"""
    try:
        connection = oracledb.connect(
            user=ORACLE_USER,
            password=ORACLE_PASSWORD,
            dsn=f"{ORACLE_HOST}:{ORACLE_PORT}/{ORACLE_SERVICE}"
        )
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT 
                CONTRACT_NUMBER AS "number", 
                TITLE AS "title", 
                TYPE_NAME AS "type", 
                PARTY_NAME AS "party", 
                DEPARTMENT_NAME AS "department", 
                ASSIGNED_TO AS "assigned", 
                CONTRACT_VALUE AS "value", 
                TO_CHAR(START_DATE, 'YYYY-MM-DD') AS "startDate", 
                TO_CHAR(EXPIRY_DATE, 'YYYY-MM-DD') AS "expiryDate", 
                STATUS AS "status",
                NVL(AUTO_RENEW, 'Y') AS "autoRenew",
                NVL(ATTACHMENT_URL, '') AS "attachment",
                NVL(NOTES, '') AS "notes",
                NVL(NOTICE_DAYS_1, 30) AS "notice1",
                NVL(NOTICE_DAYS_2, 60) AS "notice2",
                NVL(NOTICE_DAYS_3, 90) AS "notice3"
            FROM APP_CONTRACTS 
            ORDER BY CONTRACT_ID DESC
        """)
        cols = [col[0] for col in cursor.description]
        contracts = [dict(zip(cols, row)) for row in cursor.fetchall()]

        assets = []
        try:
            cursor.execute("""
                SELECT 
                    SERIAL_NUMBER AS "serialNumber", 
                    ASSET_NAME AS "assetName", 
                    ASSET_TYPE AS "assetType", 
                    CONTRACT_NUMBER AS "contractNumber", 
                    CONTRACT_TITLE AS "contractTitle", 
                    DEPARTMENT_NAME AS "department", 
                    LOCATION_DETAILS AS "locationDetails", 
                    STATUS AS "status", 
                    NOTES AS "notes"
                FROM APP_ASSETS
            """)
            a_cols = [col[0] for col in cursor.description]
            assets = [dict(zip(a_cols, row)) for row in cursor.fetchall()]
        except Exception:
            pass

        maint_logs = []
        try:
            cursor.execute("""
                SELECT 
                    MAINTENANCE_ID AS "maintenanceId",
                    SERIAL_NUMBER AS "serialNumber",
                    MAINTENANCE_TYPE AS "maintenanceType",
                    TO_CHAR(MAINTENANCE_DATE, 'YYYY-MM-DD') AS "maintenanceDate",
                    TECHNICIAN_NAME AS "technicianName",
                    PARTS_REPLACED AS "partsReplaced",
                    COST AS "cost",
                    TO_CHAR(NEXT_SERVICE_DATE, 'YYYY-MM-DD') AS "nextServiceDate"
                FROM APP_MAINTENANCE_LOGS
            """)
            m_cols = [col[0] for col in cursor.description]
            maint_logs = [dict(zip(m_cols, row)) for row in cursor.fetchall()]
        except Exception:
            pass

        connection.close()

        live_data = {
            "contracts": contracts,
            "assets": assets,
            "maintenanceLogs": maint_logs
        }
        
        target_path = os.path.join(KNOWLEDGE_FOLDER, "oracle_contracts_and_assets.json")
        with open(target_path, "w", encoding="utf-8") as dst:
            json.dump(live_data, dst, ensure_ascii=False, indent=2)

        return live_data, f"اتصال حي فوري بسيرفر أوراكل ({ORACLE_HOST}:{ORACLE_PORT}/{ORACLE_SERVICE})"

    except Exception as e_direct:
        print(f"Direct Oracle connection failed: {e_direct}")

    urls_to_try = [
        f"http://{ORACLE_HOST}:8099/api/data",
        "http://localhost:8099/api/data"
    ]
    for url in urls_to_try:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'WorkAssistantAgent/1.0'})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    raw_bytes = resp.read()
                    text = raw_bytes.decode('utf-8-sig', errors='ignore')
                    data = json.loads(text)
                    target_path = os.path.join(KNOWLEDGE_FOLDER, "oracle_contracts_and_assets.json")
                    with open(target_path, "w", encoding="utf-8") as dst:
                        json.dump(data, dst, ensure_ascii=False, indent=2)
                    return data, f"مباشر عبر السيرفر الشبكي ({url})"
        except Exception:
            pass

    kb_target = os.path.join(KNOWLEDGE_FOLDER, "oracle_contracts_and_assets.json")
    if os.path.exists(kb_target):
        try:
            with open(kb_target, "r", encoding="utf-8-sig") as f:
                return json.load(f), "كاش محلي احترازي (عند انقطاع الشبكة)"
        except Exception:
            pass

    return None, None

def get_reminders_text():
    reminders = load_reminders()
    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")
    lines = [f"--- [سجل المواعيد والمهام والتنبيهات الخاصة بالمستخدم - تاريخ اليوم الحالي: {today_str}] ---"]
    
    for idx, r in enumerate(reminders, 1):
        dt = r.get("date", "بدون تاريخ")
        title = r.get("title", "")
        notes = r.get("notes", "")
        diff_text = ""
        try:
            target_dt = datetime.datetime.strptime(dt, "%Y-%m-%d").date()
            diff = (target_dt - today).days
            if diff > 0:
                diff_text = f" (متبقي {diff} يوم)"
            elif diff == 0:
                diff_text = " (الموعد هو اليوم!)"
            else:
                diff_text = f" (انتهى الموعد منذ {abs(diff)} يوم)"
        except Exception:
            pass
        lines.append(f"{idx}. الموعد/التاريخ: {dt}{diff_text} | المهمة/الملاحظة: {title} | تفاصيل إضافية: {notes}")
    return "\n".join(lines) + "\n"

def extract_docx_text(filepath):
    try:
        with zipfile.ZipFile(filepath) as docx:
            tree = ET.fromstring(docx.read('word/document.xml'))
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            paragraphs = []
            for p in tree.iterfind('.//w:p', ns):
                texts = [node.text for node in p.iterfind('.//w:t', ns) if node.text]
                if texts:
                    paragraphs.append("".join(texts))
            return "\n".join(paragraphs)
    except Exception as e:
        return f"[خطأ في قراءة ملف Word: {e}]"

def extract_pdf_text(filepath):
    try:
        import pypdf
        reader = pypdf.PdfReader(filepath)
        pages_text = []
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                pages_text.append(txt)
        return "\n".join(pages_text)
    except ImportError:
        return "[لتفعيل قراءة ملفات PDF يرجى تثبيت مكتبة: pip install pypdf]"
    except Exception as e:
        return f"[خطأ في قراءة ملف PDF: {e}]"

def extract_excel_text(filepath):
    try:
        excel_file = pd.ExcelFile(filepath)
        sheet_texts = []
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            sheet_texts.append(f"--- ورقة عمل: {sheet_name} ---\n" + df.to_string(index=False))
        return "\n".join(sheet_texts)
    except Exception as e:
        return f"[خطأ في قراءة ملف Excel: {e}]"

def get_knowledge_files():
    if not os.path.exists(KNOWLEDGE_FOLDER):
        os.makedirs(KNOWLEDGE_FOLDER)
    files = []
    for ext in ["*.txt", "*.md", "*.sql", "*.csv", "*.json", "*.docx", "*.pdf", "*.xlsx", "*.xls"]:
        files.extend(glob.glob(os.path.join(KNOWLEDGE_FOLDER, "**", ext), recursive=True))
    return files

def load_knowledge_base():
    files = get_knowledge_files()
    knowledge_texts = []
    for filepath in files:
        filename = os.path.basename(filepath)
        content = ""
        ext = os.path.splitext(filename)[1].lower()
        
        try:
            if ext == ".docx":
                content = extract_docx_text(filepath)
            elif ext == ".pdf":
                content = extract_pdf_text(filepath)
            elif ext in [".xlsx", ".xls"]:
                content = extract_excel_text(filepath)
            else:
                for enc in ["utf-8-sig", "utf-8", "windows-1256", "latin-1"]:
                    try:
                        with open(filepath, "r", encoding=enc) as f:
                            content = f.read().strip()
                        break
                    except UnicodeDecodeError:
                        continue
                        
            if content:
                knowledge_texts.append(f"--- [ملف مرجعي: {filename}] ---\n{content}\n")
        except Exception as e:
            st.sidebar.error(f"خطأ في قراءة {filename}: {e}")
            
    reminders_txt = get_reminders_text()
    if reminders_txt:
        knowledge_texts.insert(0, reminders_txt)

    return "\n\n".join(knowledge_texts)


def clean_html_string(html_str):
    return "\n".join(line.strip() for line in html_str.splitlines() if line.strip())


def render_kpi_cards_html(contracts_list, assets_list):
    total_contracts = len(contracts_list)
    today = datetime.date.today()
    
    critical_count = 0
    warning_count = 0
    safe_count = 0
    
    for c in contracts_list:
        exp = c.get("expiryDate", "")
        if exp and exp != "-":
            try:
                exp_dt = datetime.datetime.strptime(exp, "%Y-%m-%d").date()
                diff = (exp_dt - today).days
                if diff < 0:
                    critical_count += 1
                elif diff <= 30:
                    warning_count += 1
                else:
                    safe_count += 1
            except Exception:
                safe_count += 1
        else:
            safe_count += 1

    kpi_html = f"""
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 20px; direction: rtl; text-align: right;">
<div style="background: white; border-radius: 16px; padding: 18px; border: 1px solid #e2e8f0; border-right: 6px solid #dc2626; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
<div style="display: flex; justify-content: space-between; align-items: center;">
<div>
<div style="font-size: 11px; font-weight: 800; color: #64748b; text-transform: uppercase;">إجمالي المسجل في Oracle</div>
<div style="font-size: 28px; font-weight: 900; color: #0f172a; margin-top: 4px;">{total_contracts}</div>
<div style="font-size: 11px; color: #64748b; margin-top: 2px;">عقود وقرارات محفوظة</div>
</div>
<div style="font-size: 30px; background: #fef2f2; width: 48px; height: 48px; border-radius: 14px; display: flex; align-items: center; justify-content: center; color: #dc2626;">📂</div>
</div>
</div>
<div style="background: white; border-radius: 16px; padding: 18px; border: 1px solid #fee2e2; border-right: 6px solid #b91c1c; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
<div style="display: flex; justify-content: space-between; align-items: center;">
<div>
<div style="font-size: 11px; font-weight: 800; color: #b91c1c; text-transform: uppercase;">حرجة / منتهية</div>
<div style="font-size: 28px; font-weight: 900; color: #b91c1c; margin-top: 4px;">{critical_count}</div>
<div style="font-size: 11px; color: #ef4444; margin-top: 2px;">انتهت الصلاحية وتتطلب تحرك</div>
</div>
<div style="font-size: 30px; background: #fee2e2; width: 48px; height: 48px; border-radius: 14px; display: flex; align-items: center; justify-content: center; color: #b91c1c;">🚨</div>
</div>
</div>
<div style="background: white; border-radius: 16px; padding: 18px; border: 1px solid #fef3c7; border-right: 6px solid #d97706; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
<div style="display: flex; justify-content: space-between; align-items: center;">
<div>
<div style="font-size: 11px; font-weight: 800; color: #b45309; text-transform: uppercase;">قريبة الانتهاء (30 يوم)</div>
<div style="font-size: 28px; font-weight: 900; color: #d97706; margin-top: 4px;">{warning_count}</div>
<div style="font-size: 11px; color: #d97706; margin-top: 2px;">تتطلب اتخاذ إجراء تجديد</div>
</div>
<div style="font-size: 30px; background: #fef3c7; width: 48px; height: 48px; border-radius: 14px; display: flex; align-items: center; justify-content: center; color: #d97706;">⏳</div>
</div>
</div>
<div style="background: white; border-radius: 16px; padding: 18px; border: 1px solid #d1fae5; border-right: 6px solid #059669; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
<div style="display: flex; justify-content: space-between; align-items: center;">
<div>
<div style="font-size: 11px; font-weight: 800; color: #047857; text-transform: uppercase;">آمنة وسارية</div>
<div style="font-size: 28px; font-weight: 900; color: #059669; margin-top: 4px;">{safe_count}</div>
<div style="font-size: 11px; color: #10b981; margin-top: 2px;">أكثر من 30 يوماً / سارية</div>
</div>
<div style="font-size: 30px; background: #d1fae5; width: 48px; height: 48px; border-radius: 14px; display: flex; align-items: center; justify-content: center; color: #059669;">🛡️</div>
</div>
</div>
</div>
"""
    return clean_html_string(kpi_html)


def render_contracts_html_table(contracts_list, assets_list):
    if not contracts_list:
        return "<div style='text-align: center; padding: 30px; color: #64748b; font-weight: bold;'>لا توجد عقود مسجلة أو تطابق خيارات البحث</div>"
    
    today = datetime.date.today()
    rows_html = []
    
    for idx, c in enumerate(contracts_list, 1):
        c_num = str(c.get("number", "بدون رقم"))
        c_title = str(c.get("title", ""))
        c_type = str(c.get("type", "عقد صيانة"))
        c_party = str(c.get("party", "-"))
        c_dept = str(c.get("department", "-"))
        c_assigned = str(c.get("assigned", "-"))
        c_start = str(c.get("startDate", "-"))
        c_exp = str(c.get("expiryDate", "-"))
        c_status = str(c.get("status", "ساري"))
        c_auto = str(c.get("autoRenew", "N")) == "Y"
        c_attach = str(c.get("attachment", ""))
        
        days_left_text = "غير محدد"
        badge_bg = "#f1f5f9"
        badge_color = "#475569"
        status_bg = "#dcfce7"
        status_color = "#15803d"
        
        if c_exp and c_exp != "-":
            try:
                exp_dt = datetime.datetime.strptime(c_exp, "%Y-%m-%d").date()
                diff_days = (exp_dt - today).days
                if diff_days < 0:
                    days_left_text = f"🚨 انتهى منذ {abs(diff_days)} يوم"
                    badge_bg = "#fee2e2"
                    badge_color = "#b91c1c"
                    status_bg = "#fee2e2"
                    status_color = "#b91c1c"
                    c_status = "منتهي"
                elif diff_days <= 30:
                    days_left_text = f"⚠️ متبقي {diff_days} يوم"
                    badge_bg = "#fef3c7"
                    badge_color = "#b45309"
                    status_bg = "#fef3c7"
                    status_color = "#b45309"
                    c_status = "أوشك على الانتهاء"
                elif diff_days <= 60:
                    days_left_text = f"⏳ متبقي {diff_days} يوم"
                    badge_bg = "#dbeafe"
                    badge_color = "#1d4ed8"
                    status_bg = "#dbeafe"
                    status_color = "#1d4ed8"
                else:
                    days_left_text = f"✅ متبقي {diff_days} يوم"
                    badge_bg = "#d1fae5"
                    badge_color = "#047857"
            except Exception:
                pass
                
        auto_renew_html = ""
        if c_auto:
            auto_renew_html = "<span style='font-size: 10px; background: #fef2f2; color: #dc2626; padding: 2px 6px; border-radius: 4px; border: 1px solid #fca5a5; font-weight: bold;'>🔄 تجديد تلقائي</span>"
            
        linked_count = sum(1 for a in assets_list if str(a.get("contractNumber")) == c_num or (c_title and c_title in str(a.get("contractTitle", ""))))
        assets_badge = f"<span style='font-size: 10px; background: #e0e7ff; color: #4338ca; padding: 2px 6px; border-radius: 4px; font-weight: bold;'>🖨️ المعدات ({linked_count})</span>" if linked_count > 0 else ""

        bg_color = "#ffffff" if idx % 2 == 1 else "#f8fafc"

        rows_html.append(f"""<tr style="border-bottom: 1px solid #e2e8f0; background: {bg_color};"><td style="padding: 12px 14px; vertical-align: middle;"><div style="font-weight: 800; color: #0f172a; font-size: 13px;">📑 {c_type}</div><div style="font-family: monospace; font-size: 12px; color: #dc2626; font-weight: 800;">#{c_num}</div></td><td style="padding: 12px 14px; vertical-align: middle; max-width: 340px;"><div style="font-weight: 800; color: #0f172a; font-size: 14px; line-height: 1.4;">{c_title}</div><div style="margin-top: 5px; display: flex; gap: 5px; flex-wrap: wrap;">{auto_renew_html}{assets_badge}</div></td><td style="padding: 12px 14px; vertical-align: middle; font-weight: 700; color: #334155; font-size: 13px;">{c_party}</td><td style="padding: 12px 14px; vertical-align: middle;"><div style="font-weight: 800; color: #0f172a; font-size: 13px;">🏛️ {c_dept}</div><div style="font-size: 12px; color: #64748b; margin-top: 2px;">👤 {c_assigned}</div></td><td style="padding: 12px 14px; vertical-align: middle; white-space: nowrap;"><div style="font-size: 11px; color: #64748b; font-weight: 600;">تاريخ البداية</div><div style="font-weight: 800; color: #0f172a; font-size: 13px;">📅 {c_start}</div></td><td style="padding: 12px 14px; vertical-align: middle; white-space: nowrap;"><div style="font-size: 11px; color: #991b1b; font-weight: 600;">تاريخ الانتهاء</div><div style="font-weight: 800; color: #dc2626; font-size: 13px;">⏳ {c_exp}</div></td><td style="padding: 12px 14px; vertical-align: middle; text-align: center; white-space: nowrap;"><span style="background: {badge_bg}; color: {badge_color}; padding: 6px 12px; border-radius: 12px; font-weight: 800; font-size: 12px; display: inline-block; border: 1px solid {badge_color}30;">{days_left_text}</span></td><td style="padding: 12px 14px; vertical-align: middle; text-align: center; white-space: nowrap;"><span style="background: {status_bg}; color: {status_color}; padding: 6px 14px; border-radius: 20px; font-weight: 800; font-size: 12px; display: inline-block; border: 1px solid {status_color}30;">{c_status}</span></td></tr>""")
        
    table_html = f"""
<div style="border-radius: 16px; overflow-x: auto; border: 1px solid #cbd5e1; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-top: 15px; direction: rtl; text-align: right;">
<table style="width: 100%; border-collapse: collapse; background: white; font-family: 'Cairo', 'Tajawal', sans-serif;">
<thead style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: white;">
<tr>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">النوع / الرقم</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">اسم العقد أو القرار</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">الطرف الآخر</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">الإدارة والمسؤول</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">تاريخ البداية</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">تاريخ الانتهاء</th>
<th style="padding: 14px; text-align: center; font-weight: 800; font-size: 13px;">العد التنازلي</th>
<th style="padding: 14px; text-align: center; font-weight: 800; font-size: 13px;">الحالة</th>
</tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</div>
"""
    return clean_html_string(table_html)


def render_assets_html_table(assets_list):
    if not assets_list:
        return "<div style='text-align: center; padding: 25px; color: #64748b; font-weight: bold;'>لا توجد أصول أو ماكينات تصوير مسجلة حالياً</div>"
    
    rows_html = []
    for idx, a in enumerate(assets_list, 1):
        serial = str(a.get("serialNumber", "بدون رقم تسلسلي"))
        name = str(a.get("assetName", "ماكينة تصوير"))
        atype = str(a.get("assetType", "ماكينة تصوير"))
        c_num = str(a.get("contractNumber", "-"))
        c_title = str(a.get("contractTitle", "-"))
        dept = str(a.get("department", "-"))
        loc = str(a.get("locationDetails", "-"))
        status = str(a.get("status", "يعمل"))

        status_bg = "#dcfce7"
        status_color = "#15803d"
        if "صيانة" in status or "عطل" in status:
            status_bg = "#fef3c7"
            status_color = "#b45309"
        elif "معطل" in status or "تالف" in status:
            status_bg = "#fee2e2"
            status_color = "#b91c1c"

        bg_color = "#ffffff" if idx % 2 == 1 else "#f8fafc"

        contract_info = f"📜 #{c_num} - {c_title}" if c_num and c_num != "-" else "<span style='color: #94a3b8;'>مستقل (بدون عقد)</span>"

        rows_html.append(f"""<tr style="border-bottom: 1px solid #e2e8f0; background: {bg_color};"><td style="padding: 12px 14px; vertical-align: middle;"><div style="font-weight: 800; color: #4338ca; font-size: 13px;">🖨️ {atype}</div><div style="font-family: monospace; font-size: 12px; color: #dc2626; font-weight: 800;">#{serial}</div></td><td style="padding: 12px 14px; vertical-align: middle;"><div style="font-weight: 800; color: #0f172a; font-size: 14px;">{name}</div></td><td style="padding: 12px 14px; vertical-align: middle; font-size: 12px; color: #334155; max-width: 250px;">{contract_info}</td><td style="padding: 12px 14px; vertical-align: middle;"><div style="font-weight: 800; color: #0f172a; font-size: 13px;">🏛️ {dept}</div><div style="font-size: 12px; color: #64748b; margin-top: 2px;">📍 {loc}</div></td><td style="padding: 12px 14px; vertical-align: middle; text-align: center; white-space: nowrap;"><span style="background: {status_bg}; color: {status_color}; padding: 6px 14px; border-radius: 20px; font-weight: 800; font-size: 12px; display: inline-block; border: 1px solid {status_color}30;">{status}</span></td></tr>""")

    table_html = f"""
<div style="border-radius: 16px; overflow-x: auto; border: 1px solid #cbd5e1; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-top: 15px; direction: rtl; text-align: right;">
<table style="width: 100%; border-collapse: collapse; background: white; font-family: 'Cairo', 'Tajawal', sans-serif;">
<thead style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); color: white;">
<tr>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">النوع / الرقم التسلسلي</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">اسم الأصل / ماكينة التصوير</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">العقد المرتبط</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">الإدارة والموقع</th>
<th style="padding: 14px; text-align: center; font-weight: 800; font-size: 13px;">الحالة</th>
</tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</div>
"""
    return clean_html_string(table_html)


def render_maint_html_table(maint_list):
    if not maint_list:
        return "<div style='text-align: center; padding: 25px; color: #64748b; font-weight: bold;'>لا توجد سجلات صيانة مسجلة حالياً</div>"
    
    rows_html = []
    for idx, m in enumerate(maint_list, 1):
        mid = str(m.get("maintenanceId", idx))
        serial = str(m.get("serialNumber", "-"))
        mtype = str(m.get("maintenanceType", "صيانة دورية"))
        mdate = str(m.get("maintenanceDate", "-"))
        tech = str(m.get("technicianName", "-"))
        parts = str(m.get("partsReplaced", "لا يوجد"))
        cost = m.get("cost", 0) or 0
        next_date = str(m.get("nextServiceDate", "-"))

        bg_color = "#ffffff" if idx % 2 == 1 else "#f8fafc"

        rows_html.append(f"""<tr style="border-bottom: 1px solid #e2e8f0; background: {bg_color};"><td style="padding: 12px 14px; vertical-align: middle;"><div style="font-weight: 800; color: #d97706; font-size: 13px;">🛠️ صيانة #{mid}</div><div style="font-family: monospace; font-size: 12px; color: #475569; font-weight: 800;">#{serial}</div></td><td style="padding: 12px 14px; vertical-align: middle; font-weight: 800; color: #0f172a; font-size: 13px;">{mtype}</td><td style="padding: 12px 14px; vertical-align: middle; white-space: nowrap; font-weight: 700; color: #0f172a; font-size: 13px;">📅 {mdate}</td><td style="padding: 12px 14px; vertical-align: middle; font-weight: 700; color: #334155; font-size: 13px;">👤 {tech}</td><td style="padding: 12px 14px; vertical-align: middle; font-size: 12px; color: #475569;">⚙️ {parts}</td><td style="padding: 12px 14px; vertical-align: middle; font-weight: 800; color: #059669; font-size: 13px; white-space: nowrap;">💰 {cost:,.0f} ج.م</td><td style="padding: 12px 14px; vertical-align: middle; white-space: nowrap; font-weight: 700; color: #2563eb; font-size: 13px;">⏳ {next_date}</td></tr>""")

    table_html = f"""
<div style="border-radius: 16px; overflow-x: auto; border: 1px solid #cbd5e1; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-top: 15px; direction: rtl; text-align: right;">
<table style="width: 100%; border-collapse: collapse; background: white; font-family: 'Cairo', 'Tajawal', sans-serif;">
<thead style="background: linear-gradient(135deg, #78350f 0%, #92400e 100%); color: white;">
<tr>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">الرقم / Serial</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">نوع الصيانة</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">تاريخ الصيانة</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">الفني المسؤول</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">قطع الغيار</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">التكلفة</th>
<th style="padding: 14px; text-align: right; font-weight: 800; font-size: 13px;">الموعد القادم</th>
</tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</div>
"""
    return clean_html_string(table_html)


st.set_page_config(
    page_title="المساعد الذكي لإدارة العمل والمراسلات والعقود",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Tajawal:wght@400;500;700&display=swap');

    html, body, [class*="css"], .stMarkdown, .stTextInput, .stChatMessage, div, span, button {
        font-family: 'Cairo', 'Tajawal', sans-serif !important;
        direction: rtl;
        text-align: right;
    }

    .stApp {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 50%, #e2e8f0 100%);
    }

    .hero-container {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f766e 100%);
        color: white;
        padding: 24px 32px;
        border-radius: 20px;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.25);
        margin-bottom: 24px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .hero-title {
        font-size: 26px;
        font-weight: 800;
        margin: 0;
        color: #ffffff;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .hero-subtitle {
        font-size: 14px;
        color: #94a3b8;
        margin-top: 6px;
        margin-bottom: 0;
    }

    .status-badge {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(52, 211, 153, 0.3);
        padding: 4px 14px;
        border-radius: 50px;
        font-size: 13px;
        font-weight: 600;
        display: inline-block;
    }

    .link-badge {
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        border: 1px solid rgba(96, 165, 250, 0.3);
        padding: 4px 14px;
        border-radius: 50px;
        font-size: 13px;
        font-weight: 600;
        display: inline-block;
    }

    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-left: 1px solid #e2e8f0;
        box-shadow: -4px 0 15px rgba(0, 0, 0, 0.03);
    }

    .stButton>button {
        border-radius: 12px !important;
        font-weight: 700 !important;
        transition: all 0.25s ease !important;
        border: 1px solid #cbd5e1 !important;
        background: #ffffff !important;
        color: #1e293b !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04) !important;
    }

    .stButton>button:hover {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
        color: #ffffff !important;
        border-color: #0f172a !important;
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(15, 23, 42, 0.15) !important;
    }

    .stChatMessage {
        border-radius: 16px !important;
        padding: 16px 20px !important;
        margin-bottom: 14px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03) !important;
        border: 1px solid #e2e8f0 !important;
    }
    
    [data-testid="stChatMessageUser"] {
        background-color: #ffffff !important;
        border-right: 4px solid #0284c7 !important;
    }

    [data-testid="stChatMessageAssistant"] {
        background-color: #f8fafc !important;
        border-right: 4px solid #10b981 !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: #e2e8f0;
        padding: 6px;
        border-radius: 14px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 10px 24px;
        font-weight: 700;
        color: #475569;
        border: none !important;
    }

    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.06);
    }

    .reminder-card {
        background: white;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 12px;
        border-right: 6px solid #cbd5e1;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
    }
    .reminder-card.urgent { border-right-color: #ef4444; background: #fff5f5; }
    .reminder-card.warning { border-right-color: #f59e0b; background: #fffbeb; }
    .reminder-card.normal { border-right-color: #10b981; }

    .file-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: bold;
        margin-left: 6px;
    }
    .badge-pdf { background: #fee2e2; color: #991b1b; }
    .badge-docx { background: #dbeafe; color: #1e40af; }
    .badge-xlsx { background: #dcfce7; color: #166534; }
    .badge-sql { background: #fef3c7; color: #92400e; }
    .badge-txt { background: #f3f4f6; color: #374151; }

    /* تحسين عرض الجداول ومنع اقتصاص النصوص والتواريخ */
    [data-testid="stDataFrame"] {
        width: 100% !important;
        border-radius: 12px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)


oracle_data, synced_source = sync_oracle_contracts_cache()

app_password = os.getenv("APP_PASSWORD", "")
if app_password:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.markdown("""
        <div style="text-align: center; max-width: 450px; margin: 80px auto; background: white; padding: 40px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08);">
            <h2 style="color: #0f172a;">🔒 المساعد الذكي الخاص بك</h2>
            <p style="color: #64748b;">مرحباً بك! يرجى إدخال رمز الدخول السري للوصول إلى النظام وقاعدة المعرفة.</p>
        </div>
        """, unsafe_allow_html=True)
        pwd_input = st.text_input("أدخل كلمة المرور:", type="password")
        if st.button("تسجيل الدخول", use_container_width=True):
            if pwd_input == app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("كلمة المرور غير صحيحة!")
        st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = load_history()

kb_files = get_knowledge_files()
reminders_list = load_reminders()

with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 10px 0 20px 0;">
        <div style="font-size: 42px;">💼</div>
        <h3 style="margin: 0; color: #0f172a; font-weight: 800;">المساعد الذكي للعمل</h3>
        <p style="font-size: 13px; color: #64748b; margin-top: 4px;">مربوط حياً بـ Oracle 192.168.200.10</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.subheader("⚙️ إعدادات النموذج الذكي")
    env_api_key = os.getenv("GEMINI_API_KEY", "")
    api_key = st.text_input("مفتاح Gemini API:", value=env_api_key, type="password", help="احصل عليه من aistudio.google.com")
    
    model_name = st.selectbox(
        "النموذج النشط:",
        ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"],
        index=0
    )

    st.divider()
    
    st.subheader("🌐 اتصال Oracle المباشر الحي")
    if oracle_data:
        st.success(f"✅ {synced_source}")
        if st.button("⚡ اتصال واستعلام حي الآن من Oracle"):
            o_data, o_src = sync_oracle_contracts_cache()
            st.success(f"تم تحديث الاستعلام اللحظي: {o_src}")
            st.rerun()
    else:
        st.error("❌ تعذر الاتصال المباشر. انقر لإعادة الاتصال.")
        if st.button("🔄 إعادة محاولة الاتصال بـ Oracle"):
            o_data, o_src = sync_oracle_contracts_cache()
            st.rerun()

    st.divider()
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.metric("📁 ملفات المعرفة", len(kb_files))
    with col_s2:
        st.metric("📅 المهام المسجلة", len(reminders_list))

    st.divider()
    st.subheader("📚 ملفات قاعدة المعرفة:")
    if kb_files:
        for f in kb_files:
            fname = os.path.basename(f)
            ext = os.path.splitext(fname)[1].lower().replace(".", "")
            badge_cls = f"badge-{ext}" if ext in ["pdf", "docx", "xlsx", "sql", "txt"] else "badge-txt"
            st.markdown(f"📄 <span class='file-badge {badge_cls}'>{ext.upper()}</span> `{fname}`", unsafe_allow_html=True)
    else:
        st.info("لا توجد ملفات في مجلد المعرفة.")

    st.divider()
    uploaded_file = st.file_uploader("➕ إضافة ملف لقاعدة المعرفة:", type=["txt", "md", "sql", "csv", "json", "docx", "pdf", "xlsx", "xls"])
    if uploaded_file is not None:
        save_path = os.path.join(KNOWLEDGE_FOLDER, uploaded_file.name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"تم حفظ الملف: {uploaded_file.name}")
        st.rerun()

    st.divider()
    st.subheader("💾 حفظ وأرشفة المعاملات:")
    if len(st.session_state.messages) > 1:
        full_text = "\n\n" + "="*50 + "\n\n".join([f"[{'المستخدم' if m['role']=='user' else 'المساعد'}]:\n{m['content']}" for m in st.session_state.messages])
        st.download_button(
            "💾 تصدير محادثة الخطابات (.txt)",
            data=full_text,
            file_name="سجل_الخطابات_والمعاملات.txt",
            mime="text/plain",
            use_container_width=True
        )

    if st.button("🗑️ مسح المحادثة والبدء من جديد", use_container_width=True):
        st.session_state.messages = [
            {"role": "assistant", "content": "أهلاً بك يا فندم! 👋 أنا مساعدك الذكي المربوط حياً وبشكل مباشر بقاعدة بيانات أوراكل (192.168.200.10) والمراسلات.\n\nكيف يمكنني دعمك اليوم؟ يمكنك طلب صياغة خطاب، مراجعة العقود المحدثة لحظياً، أو استعلامات أوراكل."}
        ]
        save_history(st.session_state.messages)
        st.rerun()


# الهيدر الترحيبي الجذاب
st.markdown("""
<div class="hero-container">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
        <div>
            <h1 class="hero-title">🤖 المساعد الذكي لإدارة العمل والمراسلات والعقود</h1>
            <p class="hero-subtitle">ربط فوري ولحظي مباشر بقاعدة بيانات أوراكل (192.168.200.10:1521/XEPDB1)</p>
        </div>
        <div style="display: flex; gap: 10px;">
            <span class="status-badge">🟢 اتصال مباشر بـ Oracle</span>
            <span class="link-badge">🌐 192.168.200.10:1521</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


tab_chat, tab_reminders, tab_contracts_app = st.tabs([
    "💬 محادثة المساعد وصياغة الخطابات", 
    "📅 جدول المواعيد والمهام والتنبيهات",
    "📊 لوحة عقود أوراكل الحية (Direct Oracle Live)"
])

with tab_contracts_app:
    st.markdown("### 📊 لوحة استعلامات أوراكل الحية المباشرة (Oracle Direct DB)")
    st.caption("يستعرض هذا القسم البيانات المجلوبة حياً ومباشرة من جدول APP_CONTRACTS بدون أي بيانات ثنائية ثابتة.")

    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 1])
    with col_btn1:
        st.link_button("🌐 فتح تطبيق العقود (192.168.200.10:8099)", "http://192.168.200.10:8099", use_container_width=True)
    with col_btn2:
        st.link_button("💻 فتح التوصيل المحلي (Localhost:8099)", "http://localhost:8099", use_container_width=True)
    with col_btn3:
        if st.button("⚡ استعلام حي الآن"):
            o_data, o_src = sync_oracle_contracts_cache()
            st.success(f"تم الاستعلام: {o_src}")
            st.rerun()

    st.divider()

    if oracle_data:
        contracts_list = oracle_data.get("contracts", [])
        assets_list = oracle_data.get("assets", [])
        maint_list = oracle_data.get("maintenanceLogs", [])

        st.markdown(render_kpi_cards_html(contracts_list, assets_list), unsafe_allow_html=True)

        st.divider()

        tab_c1, tab_c2, tab_c3, tab_c4, tab_c5 = st.tabs([
            "📋 الجدول العام للعقود (العرض المطابق لـ 8099)",
            "📑 شاشة ملف العقد التفصيلي",
            "🖨️ ماكينات التصوير والأصول",
            "🛠️ سجلات الصيانة والتكلفة",
            "🚨 التنبيهات وإشعارات التجديد"
        ])

        with tab_c1:
            st.markdown("#### 📋 جدول العقود الحية المباشرة (مطابق لتصميم تطبيق أوراكل 8099)")
            c_search, c_dept_filter = st.columns([3, 2])
            with c_search:
                search_term = st.text_input("🔍 بحث برقم العقد أو الاسم أو الجهة:", key="c_search_input")
            with c_dept_filter:
                depts = ["الكل"] + sorted(list(set(c.get("department", "") for c in contracts_list if c.get("department"))))
                sel_dept = st.selectbox("🏢 تصفية حسب الإدارة المسؤولة:", depts, key="c_dept_select")

            filtered_contracts = contracts_list
            if search_term:
                filtered_contracts = [c for c in filtered_contracts if search_term in str(c.get("number", "")) or search_term in str(c.get("title", "")) or search_term in str(c.get("party", ""))]
            if sel_dept != "الكل":
                filtered_contracts = [c for c in filtered_contracts if c.get("department") == sel_dept]

            # عرض الجدول بتنسيق HTML المباشر المطابق لتطبيق أوراكل 8099
            st.markdown(render_contracts_html_table(filtered_contracts, assets_list), unsafe_allow_html=True)
            
            with st.expander("📊 عرض كجدول بيانات تفاعلي (Dataframe Grid)"):
                if filtered_contracts:
                    df_contracts = pd.DataFrame(filtered_contracts)
                    rename_map = {
                        "number": "رقم العقد",
                        "title": "عنوان العقد / الموضوع",
                        "type": "النوع",
                        "party": "الجهة المتعاقدة",
                        "department": "الإدارة المسؤولة",
                        "assigned": "المسؤول",
                        "value": "القيمة",
                        "startDate": "تاريخ البداية",
                        "expiryDate": "تاريخ الانتهاء",
                        "status": "الحالة"
                    }
                    cols_to_show = [c for c in rename_map.keys() if c in df_contracts.columns]
                    df_view = df_contracts[cols_to_show].rename(columns=rename_map)
                    
                    st.dataframe(
                        df_view,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "رقم العقد": st.column_config.TextColumn("رقم العقد", width="medium"),
                            "عنوان العقد / الموضوع": st.column_config.TextColumn("عنوان العقد / الموضوع", width="large"),
                            "النوع": st.column_config.TextColumn("النوع", width="medium"),
                            "الجهة المتعاقدة": st.column_config.TextColumn("الجهة المتعاقدة", width="large"),
                            "الإدارة المسؤولة": st.column_config.TextColumn("الإدارة المسؤولة", width="medium"),
                            "المسؤول": st.column_config.TextColumn("المسؤول", width="medium"),
                            "القيمة": st.column_config.NumberColumn("القيمة (ج.م)", format="%d ج.م", width="medium"),
                            "تاريخ البداية": st.column_config.TextColumn("تاريخ البداية", width="medium"),
                            "تاريخ الانتهاء": st.column_config.TextColumn("تاريخ الانتهاء", width="medium"),
                            "الحالة": st.column_config.TextColumn("الحالة", width="small")
                        }
                    )

        with tab_c2:
            st.markdown("#### 📑 شاشة ملف العقد الشاملة (Dossier Screen)")
            st.caption("اختر أي عقد من القائمة لاستعراض ملفه الكامل، ماكينات التصوير المرتبطة به، وسجلات صيانته والإجراءات المتاحة.")
            
            contract_options = [f"[{c.get('number')}] - {c.get('title')}" for c in contracts_list]
            selected_contract_str = st.selectbox("👇 اختر العقد المطلوبة تفاصيله:", contract_options, key="select_contract_dossier")
            
            if selected_contract_str:
                sel_num = selected_contract_str.split("]")[0].replace("[", "").strip()
                contract_data = next((c for c in contracts_list if str(c.get("number")) == sel_num), None)
                
                if contract_data:
                    st.markdown(f"""
                    <div style="background: white; padding: 20px; border-radius: 16px; border-right: 6px solid #0f766e; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 20px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                            <h3 style="margin: 0; color: #0f172a;">📜 عقد رقم {contract_data.get('number')}: {contract_data.get('title')}</h3>
                            <span style="background: #e0f2fe; color: #0369a1; font-weight: bold; padding: 6px 16px; border-radius: 20px;">الحالة: {contract_data.get('status')}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        val_num = contract_data.get('value', 0) or 0
                        st.metric("💰 قيمة العقد", f"{val_num:,.0f} ج.م")
                    with m2:
                        st.metric("📅 تاريخ البداية", str(contract_data.get('startDate', '-')))
                    with m3:
                        st.metric("⏳ تاريخ الانتهاء", str(contract_data.get('expiryDate', '-')))
                    with m4:
                        st.metric("🔄 التجديد التلقائي", "نعم" if contract_data.get('autoRenew') == 'Y' else "لا")

                    st.divider()

                    info_col1, info_col2 = st.columns(2)
                    with info_col1:
                        st.markdown(f"**🏢 الإدارة المسؤولة:** {contract_data.get('department', '-')}")
                        st.markdown(f"**👤 المسؤول المباشر:** {contract_data.get('assigned', '-')}")
                        st.markdown(f"**📑 نوع العقد:** {contract_data.get('type', '-')}")
                    with info_col2:
                        st.markdown(f"**🤝 الجهة المتعاقدة:** {contract_data.get('party', '-')}")
                        st.markdown(f"**🔔 فترة التنبيه (أيام):** {contract_data.get('notice1', 30)} يوم")
                        st.markdown(f"**📝 ملاحظات:** {contract_data.get('notes', 'لا توجد ملاحظات إضافية')}")

                    if contract_data.get("attachment"):
                        st.markdown(f"📎 **المرفق:** [عرض ملف العقد]({contract_data.get('attachment')})")

                    st.divider()
                    
                    st.markdown("##### 🖨️ الأصول وماكينات التصوير المربوطة بهذا العقد:")
                    linked_assets = [a for a in assets_list if str(a.get("contractNumber")) == str(contract_data.get("number")) or (contract_data.get("title") and str(contract_data.get("title")) in str(a.get("contractTitle", "")))]
                    
                    if linked_assets:
                        st.markdown(render_assets_html_table(linked_assets), unsafe_allow_html=True)
                        
                        serials = [a.get("serialNumber") for a in linked_assets if a.get("serialNumber")]
                        linked_maint = [m for m in maint_list if m.get("serialNumber") in serials]
                        
                        st.markdown("##### 🛠️ سجلات الصيانة السابقة لأصول هذا العقد:")
                        if linked_maint:
                            st.markdown(render_maint_html_table(linked_maint), unsafe_allow_html=True)
                        else:
                            st.info("لا توجد سجلات صيانة مسجلة لهذه الأصول حتى الآن.")
                    else:
                        st.info("لا توجد أصول أو ماكينات تصوير مربوطة بهذا العقد رسمياً في الجدول.")

        with tab_c3:
            st.markdown("#### 🖨️ إدارة ماكينات التصوير والأصول الموزعة (APP_ASSETS)")
            if assets_list:
                a_search = st.text_input("🔍 بحث بالرقم التسلسلي أو اسم الأصل أو الإدارة:", key="a_search_input")
                filt_assets = assets_list
                if a_search:
                    filt_assets = [a for a in filt_assets if a_search in str(a.get("serialNumber", "")) or a_search in str(a.get("assetName", "")) or a_search in str(a.get("department", ""))]
                
                st.markdown(render_assets_html_table(filt_assets), unsafe_allow_html=True)
            else:
                st.info("لا توجد أصول مسجلة حالياً.")

        with tab_c4:
            st.markdown("#### 🛠️ سجلات الصيانة والتكاليف (APP_MAINTENANCE_LOGS)")
            if maint_list:
                m_search = st.text_input("🔍 بحث بالرقم التسلسلي أو اسم الفني:", key="m_search_input")
                filt_maint = maint_list
                if m_search:
                    filt_maint = [m for m in filt_maint if m_search in str(m.get("serialNumber", "")) or m_search in str(m.get("technicianName", ""))]
                
                st.markdown(render_maint_html_table(filt_maint), unsafe_allow_html=True)
            else:
                st.info("لا توجد سجلات صيانة مسجلة.")

        with tab_c5:
            st.markdown("#### 🚨 التنبيهات ومتابعة التجديدات الحية")
            st.caption("استعراض العقود التي تتطلب اتخاذ إجراءات تجديد أو متابعة عاجلة.")
            
            exp_contracts = [c for c in contracts_list if "2026" in str(c.get("expiryDate", "")) or c.get("status") in ["أوشك على الانتهاء", "EXPIRING_SOON"]]
            if exp_contracts:
                for ec in exp_contracts:
                    st.warning(f"⚠️ **عقد رقم {ec.get('number')}**: {ec.get('title')} | **الجهة:** {ec.get('party')} | **تاريخ الانتهاء:** {ec.get('expiryDate')} | **الإدارة:** {ec.get('department')}")
            else:
                st.success("✅ جميع العقود سارية ولا يوجد عقود حرجة منتهية حالياً.")
    else:
        st.warning("⚠️ تعذر تنفيذ استعلام أوراكل الحي. انقر على زر إعادة المحاولة أعلاه.")


with tab_reminders:
    st.markdown("### 📅 سجل المواعيد والمهام والملاحظات الخاصة بك")
    st.caption("يقوم المساعد الذكي بقراءة هذا السجل تلقائياً لتنبيهك ومتابعة تواريخ انتهاء العقود والمواعيد!")

    with st.expander("➕ إضافة موعد أو مهمة أو عقد جديد للسجل", expanded=True):
        with st.form("new_reminder_form", clear_on_submit=True):
            r_title = st.text_input("موضوع المهمة / العقد (مثال: تجديد عقد استضافة الموقع، متابعة صيانة ماكينات التصوير):")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                r_date = st.date_input("التاريخ المستهدف / تاريخ الانتهاء:", value=datetime.date.today() + datetime.timedelta(days=7))
            with col_d2:
                r_notes = st.text_input("تفاصيل وملاحظات (أرقام العقود، الجهة المتعاقدة، الإشارات):")
            
            submitted = st.form_submit_button("💾 حفظ في سجل المساعد الذكي")
            if submitted and r_title:
                reminders_list.append({
                    "id": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
                    "title": r_title,
                    "date": r_date.strftime("%Y-%m-%d"),
                    "notes": r_notes
                })
                save_reminders(reminders_list)
                st.success(f"تم حفظ: {r_title}")
                st.rerun()

    current_reminders = load_reminders()
    if current_reminders:
        st.markdown(f"#### 📋 المواعيد المسجلة حالياً ({len(current_reminders)}):")
        today = datetime.date.today()
        for idx, item in enumerate(current_reminders):
            dt_str = item.get("date", "")
            title = item.get("title", "")
            notes = item.get("notes", "")
            
            card_class = "normal"
            diff_badge = ""
            try:
                t_date = datetime.datetime.strptime(dt_str, "%Y-%m-%d").date()
                days_left = (t_date - today).days
                if days_left > 30:
                    diff_badge = f"⏳ متبقي {days_left} يوماً"
                    card_class = "normal"
                elif 7 < days_left <= 30:
                    diff_badge = f"⚠️ تنبيه متوسط: متبقي {days_left} يوماً"
                    card_class = "warning"
                elif 0 <= days_left <= 7:
                    diff_badge = f"🚨 تنبيه حرج: متبقي {days_left} أيام فقط!"
                    card_class = "urgent"
                else:
                    diff_badge = f"❌ انتهى الموعد منذ {abs(days_left)} يوماً"
                    card_class = "urgent"
            except Exception:
                diff_badge = dt_str

            col_info, col_del = st.columns([5, 1])
            with col_info:
                st.markdown(f"""
                <div class="reminder-card {card_class}">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 16px; font-weight: 700; color: #0f172a;">📌 {title}</span>
                        <span style="font-size: 13px; font-weight: 600; padding: 4px 10px; border-radius: 20px; background: rgba(0,0,0,0.05);">{diff_badge}</span>
                    </div>
                    <div style="font-size: 13px; color: #64748b; margin-top: 6px;">📅 التاريخ المحدد: <code>{dt_str}</code> {f'| 📝 {notes}' if notes else ''}</div>
                </div>
                """, unsafe_allow_html=True)
            with col_del:
                if st.button("🗑️ حذف", key=f"del_rem_{item.get('id', idx)}"):
                    current_reminders.pop(idx)
                    save_reminders(current_reminders)
                    st.rerun()
    else:
        st.info("لا توجد مواعيد أو مهام مسجلة حالياً.")

with tab_chat:
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and idx > 0 and len(msg["content"]) > 40:
                st.download_button(
                    label="📥 تحميل هذا الخطاب (.txt)",
                    data=msg["content"],
                    file_name=f"خطاب_رقم_{idx}.txt",
                    key=f"dl_letter_{idx}",
                    mime="text/plain"
                )

    st.markdown("<h4 style='color: #0f172a; margin-top: 20px;'>⚡ إجراءات واستعلامات سريعة:</h4>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    quick_prompt = None
    with col1:
        if st.button("📑 استعلام حي لعقود Oracle"):
            quick_prompt = "استخرج لي ملخص العقود والتراخيص الحية المجلوبة حياً ومباشرة من قاعدة بيانات أوراكل APP_CONTRACTS."
    with col2:
        if st.button("🖨️ حالة ماكينات التصوير"):
            quick_prompt = "ما هي حالة ماكينات التصوير والأصول الموزعة على الإدارات وسجلات الصيانة الأخيرة؟"
    with col3:
        if st.button("📝 صياغة خطاب عاجل"):
            quick_prompt = "أريد صياغة خطاب رسمي عاجل موجه لجهة معينة بخصوص طلب سرعة إفادتنا بنتائج التدقيق المالي."
    with col4:
        if st.button("🔍 استعلام SQL للعقود"):
            quick_prompt = "اكتب لي استعلام SQL دقيق من جدول APP_CONTRACTS لاستخراج العقود التي ستنتهي خلال الـ 30 يوماً القادمة."

    st.markdown("<br>", unsafe_allow_html=True)
    
    chat_file = st.file_uploader("📎 رفع مستند/خطاب/صورة لتحليلها فوراً في هذه المحادثة:", type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "xlsx"], key="chat_doc_uploader")

    user_input = st.chat_input("اكتب استفسارك أو طلبك هنا...") or quick_prompt

    if user_input:
        if not api_key:
            st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي أولاً.")
        else:
            file_context = ""
            if chat_file is not None:
                fname = chat_file.name
                fext = os.path.splitext(fname)[1].lower()
                st.info(f"جاري معالجة الملف المرفق: {fname}")
                
                try:
                    if fext == ".pdf":
                        import pypdf
                        reader = pypdf.PdfReader(chat_file)
                        pdf_texts = [p.extract_text() for p in reader.pages if p.extract_text()]
                        file_context = f"\n\n--- [محتوى الملف المرفق: {fname}] ---\n" + "\n".join(pdf_texts)
                    elif fext == ".docx":
                        save_temp = os.path.join(KNOWLEDGE_FOLDER, f"temp_{fname}")
                        with open(save_temp, "wb") as f:
                            f.write(chat_file.getbuffer())
                        file_context = f"\n\n--- [محتوى الملف المرفق: {fname}] ---\n" + extract_docx_text(save_temp)
                        try:
                            os.remove(save_temp)
                        except Exception:
                            pass
                    elif fext in [".xlsx", ".xls"]:
                        save_temp = os.path.join(KNOWLEDGE_FOLDER, f"temp_{fname}")
                        with open(save_temp, "wb") as f:
                            f.write(chat_file.getbuffer())
                        file_context = f"\n\n--- [محتوى الملف المرفق: {fname}] ---\n" + extract_excel_text(save_temp)
                        try:
                            os.remove(save_temp)
                        except Exception:
                            pass
                    elif fext in [".txt", ".md", ".sql", ".csv", ".json"]:
                        content_str = chat_file.read().decode("utf-8-sig", errors="ignore")
                        file_context = f"\n\n--- [محتوى الملف المرفق: {fname}] ---\n" + content_str
                except Exception as e_file:
                    st.warning(f"تعذر استخراج محتوى الملف {fname}: {e_file}")

            full_user_content = user_input + file_context

            st.session_state.messages.append({"role": "user", "content": full_user_content})
            save_history(st.session_state.messages)
            with st.chat_message("user"):
                st.markdown(full_user_content)

            with st.chat_message("assistant"):
                with st.spinner("جاري الاتصال المباشر والتفكير..."):
                    try:
                        knowledge = load_knowledge_base()
                        system_instruction = f"""
أنت مساعد ذكي إداري وتقني مخصص ومحترف. وظيفتك الأساسية هي مساعدة المستخدم في أعماله اليومية (إدارة الخطابات، العقود، المواعيد النهائية، وقواعد البيانات).
لديك وصول كامل ومباشر لقاعدة المعرفة المرفقة أدناه وتتضمن بيانات العقود الحية المجلوبة المباشرة من قاعدة بيانات أوراكل (192.168.200.10:1521/XEPDB1):

قواعد العمل:
1. استند دائماً إلى القواعد والمعلومات المجلوبة حياً ومباشرة من أوراكل.
2. عند إجابة استفسارات العقود والتراخيص، اذكر البيانات المحدثة بدقة من جدول APP_CONTRACTS بدون أي تعديل أو بيانات افتراضية.
3. عند كتابة الخطابات، استخدم الصيغ الرسمية والمهذبة (سعادة / السيد... وتفضلوا بقبول فائق الاحترام).
4. عند كتابة استعلامات Oracle SQL، التزم بأسماء الجداول والحقول المذكورة في المعرفة بدقة (APP_CONTRACTS, APP_CONTRACT_RENEWALS, APP_CONTRACT_ACTIONS, APP_ASSETS, APP_MAINTENANCE_LOGS).
5. إجاباتك يجب أن تكون منظمة وواضحة وباللغة العربية الفصحى المناسبة لبيئة العمل.

--- بداية قاعدة المعرفة المحدثة لحصلتها حياً من أوراكل ---
{knowledge if knowledge else "لا توجد ملفات معرفة حالياً."}
--- نهاية قاعدة المعرفة ---
"""
                        client = genai.Client(api_key=api_key)
                        
                        formatted_contents = []
                        for m in st.session_state.messages:
                            role = "user" if m["role"] == "user" else "model"
                            formatted_contents.append(types.Content(
                                role=role,
                                parts=[types.Part.from_text(text=m["content"])]
                            ))

                        response_stream = client.models.generate_content_stream(
                            model=model_name,
                            contents=formatted_contents,
                            config=types.GenerateContentConfig(
                                system_instruction=system_instruction,
                                temperature=0.3,
                            )
                        )
                        
                        def stream_generator():
                            for chunk in response_stream:
                                if chunk.text:
                                    yield chunk.text

                        reply = st.write_stream(stream_generator())
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                        save_history(st.session_state.messages)

                    except Exception as e:
                        err_msg = f"عذراً، حدث خطأ أثناء الاتصال أو تجاوز الحد المسموح: {e}"
                        st.error(err_msg)
                        st.session_state.messages.append({"role": "assistant", "content": err_msg})
                        save_history(st.session_state.messages)
