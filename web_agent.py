import os
import glob
import json
import datetime
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "chat_history.json")
REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "reminders.json")

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return [
        {"role": "assistant", "content": "مرحباً بك يا فندم! أنا مساعدك الذكي الخاص بعملك. كيف يمكنني مساعدتك اليوم؟ يمكنك أن تطلب مني صياغة خطاب رسمي، أو فحص مواعيد العقود، أو كتابة استعلام لقاعدة البيانات."}
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
            with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
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

def get_reminders_text():
    reminders = load_reminders()
    if not reminders:
        return ""
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



st.set_page_config(
    page_title="المساعد الذكي لإدارة العمل والمراسلات",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# تطبيق اتجاه اليمين لليسار (RTL) بالكامل على الواجهة
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    html, body, [class*="css"], .stMarkdown, .stTextInput, .stChatMessage {
        font-family: 'Cairo', sans-serif !important;
        direction: rtl;
        text-align: right;
    }
    .stChatMessage {
        direction: rtl !important;
        text-align: right !important;
    }
    .stSidebar {
        direction: rtl;
        text-align: right;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

KNOWLEDGE_FOLDER = os.path.join(os.path.dirname(__file__), "knowledge_base")

import zipfile
import xml.etree.ElementTree as ET

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
        for i, page in enumerate(reader.pages):
            txt = page.extract_text()
            if txt:
                pages_text.append(txt)
        return "\n".join(pages_text)
    except ImportError:
        return "[لتفعيل قراءة ملفات PDF يرجى تثبيت مكتبة: pip install pypdf]"
    except Exception as e:
        return f"[خطأ في قراءة ملف PDF: {e}]"

def get_knowledge_files():
    if not os.path.exists(KNOWLEDGE_FOLDER):
        os.makedirs(KNOWLEDGE_FOLDER)
    files = []
    for ext in ["*.txt", "*.md", "*.sql", "*.csv", "*.json", "*.docx", "*.pdf"]:
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
            else:
                for enc in ["utf-8", "utf-8-sig", "windows-1256", "latin-1"]:
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



# فحص كلمة المرور الاختيارية لحماية الرابط السحابي
app_password = ""
try:
    app_password = st.secrets.get("APP_PASSWORD", "")
except Exception:
    pass
if not app_password:
    app_password = os.getenv("APP_PASSWORD", "")

if app_password:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔒 المساعد الذكي الخاص بك")
        st.write("هذا المساعد محمي برمز سري لضمان خصوصية عملك ومستنداتك.")
        pwd_input = st.text_input("أدخل كلمة المرور:", type="password")
        if st.button("تسجيل الدخول"):
            if pwd_input == app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("كلمة المرور غير صحيحة!")
        st.stop()

# تهيئة سجل المحادثة وقراءته من الملف المحفوظ تلقائياً فوراً في البداية
if "messages" not in st.session_state:
    st.session_state.messages = load_history()

# الشريط الجانبي
with st.sidebar:
    st.title("💼 إعدادات المساعد")
    
    env_api_key = ""
    try:
        env_api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass
    if not env_api_key:
        env_api_key = os.getenv("GEMINI_API_KEY", "")
        
    api_key = st.text_input("مفتاح Gemini API:", value=env_api_key, type="password", help="احصل عليه مجاناً من aistudio.google.com")
    
    model_name = st.selectbox(
        "النموذج الذكي:",
        ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"],
        index=0
    )


    st.divider()
    st.subheader("📚 ملفات قاعدة المعرفة:")
    files = get_knowledge_files()
    if files:
        for f in files:
            st.write(f"📄 `{os.path.basename(f)}`")
    else:
        st.info("لا توجد ملفات في مجلد المعرفة.")

    st.divider()
    # رفع ملف جديد مباشرة
    uploaded_file = st.file_uploader("إضافة ملف لقاعدة المعرفة:", type=["txt", "md", "sql", "csv", "json", "docx", "pdf"])
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
            "💾 تحميل كل الخطابات والمحادثة (.txt)",
            data=full_text,
            file_name="سجل_الخطابات_والمعاملات.txt",
            mime="text/plain",
            use_container_width=True
        )
    else:
        st.caption("💡 سيظهر زر التحميل الكامل هنا فور كتابة أي خطاب.")

    if st.button("🗑️ مسح المحادثة والبدء من جديد", use_container_width=True):
        st.session_state.messages = [
            {"role": "assistant", "content": "مرحباً بك يا فندم! أنا مساعدك الذكي الخاص بعملك. كيف يمكنني مساعدتك اليوم؟ يمكنك أن تطلب مني صياغة خطاب رسمي، أو فحص مواعيد العقود، أو كتابة استعلام لقاعدة البيانات."}
        ]
        save_history(st.session_state.messages)
        st.rerun()

# الشاشة الرئيسية
st.title("🤖 المساعد الذكي لإدارة العمل والمراسلات والعقود")
st.caption("مساعدك المتخصص في صياغة الخطابات، مراجعة العقود، والاستعلامات الإدارية والتقنية.")

# تنظيم الواجهة في تبويبين: المحادثة وإدارة المواعيد
tab_chat, tab_reminders = st.tabs(["💬 محادثة المساعد وصياغة الخطابات", "📅 مواعيدي ومهامي وتنبيهاتي الخاصة"])

with tab_reminders:
    st.subheader("📅 سجل المواعيد والمهام والملاحظات الخاصة بك")
    st.caption("المساعد الذكي يقرأ هذه القائمة تلقائياً وسيفكرك بها ويحسب لك الأيام المتبقية عندما تسأله!")

    with st.expander("➕ إضافة موعد أو مهمة أو ملاحظة جديدة", expanded=True):
        with st.form("new_reminder_form", clear_on_submit=True):
            r_title = st.text_input("الموضوع / المهمة (مثال: موعد تجديد رخصة المقر، متابعة عقد التوريد رقم 102):")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                r_date = st.date_input("التاريخ المستهدف:", value=datetime.date.today() + datetime.timedelta(days=7))
            with col_d2:
                r_notes = st.text_input("ملاحظات خاصة (أرقام ملفات، أسماء مسؤولين، تفاصيل):")
            
            submitted = st.form_submit_button("💾 حفظ في سجل المساعد")
            if submitted and r_title:
                reminders_list = load_reminders()
                reminders_list.append({
                    "id": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
                    "title": r_title,
                    "date": r_date.strftime("%Y-%m-%d"),
                    "notes": r_notes
                })
                save_reminders(reminders_list)
                st.success(f"تم حفظ: {r_title}")
                st.rerun()

    # استعراض المواعيد المحفوظة
    current_reminders = load_reminders()
    if current_reminders:
        st.subheader(f"📋 المواعيد والمهام المسجلة ({len(current_reminders)}):")
        today = datetime.date.today()
        for idx, item in enumerate(current_reminders):
            dt_str = item.get("date", "")
            title = item.get("title", "")
            notes = item.get("notes", "")
            
            diff_text = ""
            try:
                t_date = datetime.datetime.strptime(dt_str, "%Y-%m-%d").date()
                days_left = (t_date - today).days
                if days_left > 7:
                    diff_text = f"⏳ متبقي {days_left} يوماً"
                elif 0 <= days_left <= 7:
                    diff_text = f"🚨 عاجل: متبقي {days_left} أيام فقط!"
                else:
                    diff_text = f"⚠️ انتهى منذ {abs(days_left)} يوماً"
            except Exception:
                diff_text = dt_str

            col_info, col_del = st.columns([5, 1])
            with col_info:
                st.markdown(f"**📌 {title}** — `{dt_str}` ({diff_text})")
                if notes:
                    st.caption(f"📝 {notes}")
            with col_del:
                if st.button("🗑️ حذف", key=f"del_rem_{item.get('id', idx)}"):
                    current_reminders.pop(idx)
                    save_reminders(current_reminders)
                    st.rerun()
            st.divider()
    else:
        st.info("لا توجد مواعيد أو مهام مسجلة حالياً. استخدم النموذج أعلاه لتسجيل أول موعد.")

with tab_chat:
    # عرض الرسائل السابقة مع زر تحميل أسفل كل خطاب
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

    # أزرار إجراءات سريعة
    col1, col2, col3, col4 = st.columns(4)
    quick_prompt = None
    with col1:
        if st.button("📅 فكرني بمواعيدي ومهامي"):
            quick_prompt = "ما هي المواعيد والمهام والتنبيهات المسجلة القادمة؟ وما الذي يجب أن أنجزه أولاً بحسب تاريخ اليوم؟"
    with col2:
        if st.button("📝 صياغة خطاب عاجل"):
            quick_prompt = "أريد صياغة خطاب رسمي عاجل موجه لجهة معينة بخصوص طلب سرعة إفادتنا بنتائج التدقيق المالي."
    with col3:
        if st.button("⏳ شروط تنبيهات العقود"):
            quick_prompt = "ما هي فترات التنبيه المعتمدة للعقود قبل انتهائها، وكيف يتم تصنيف درجات الأولوية للمراسلات؟"
    with col4:
        if st.button("🔍 استعلام SQL للعقود"):
            quick_prompt = "اكتب لي استعلام SQL دقيق من جدول CONTRACTS لاستخراج العقود التي ستنتهي خلال الـ 30 يوماً القادمة."


    user_input = st.chat_input("اكتب استفسارك أو طلبك هنا...") or quick_prompt

    if user_input:
        if not api_key:
            st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي أولاً.")
        else:
            # إضافة رسالة المستخدم
            st.session_state.messages.append({"role": "user", "content": user_input})
            save_history(st.session_state.messages)
            with st.chat_message("user"):
                st.markdown(user_input)

            # استدعاء النموذج
            with st.chat_message("assistant"):
                with st.spinner("جاري التفكير وصياغة الرد..."):
                    try:
                        knowledge = load_knowledge_base()
                        system_instruction = f"""
أنت مساعد ذكي إداري وتقني مخصص ومحترف. وظيفتك الأساسية هي مساعدة المستخدم في أعماله اليومية (إدارة الخطابات، العقود، المواعيد النهائية، وقواعد البيانات).
لديك وصول كامل لقاعدة المعرفة المرفقة أدناه الخاصة بنظام المستخدم:

قواعد العمل:
1. استند دائماً إلى القواعد والمعلومات الموجودة في قاعدة المعرفة.
2. عند كتابة الخطابات، استخدم الصيغ الرسمية والمهذبة (سعادة / السيد... وتفضلوا بقبول فائق الاحترام).
3. عند كتابة استعلامات Oracle SQL، التزم بأسماء الجداول والحقول المذكورة في المعرفة بدقة.
4. إجاباتك يجب أن تكون منظمة وواضحة وباللغة العربية الفصحى المناسبة لبيئة العمل.

--- بداية قاعدة المعرفة ---
{knowledge if knowledge else "لا توجد ملفات معرفة حالياً."}
--- نهاية قاعدة المعرفة ---
"""
                        client = genai.Client(api_key=api_key)
                        
                        # تجهيز المحادثة مع السجل
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



