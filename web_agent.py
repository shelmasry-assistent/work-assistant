import os
import glob
import json
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "chat_history.json")

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
col1, col2, col3 = st.columns(3)
quick_prompt = None
with col1:
    if st.button("📝 صياغة خطاب رسمي عاجل"):
        quick_prompt = "أريد صياغة خطاب رسمي عاجل موجه لجهة معينة بخصوص طلب سرعة إفادتنا بنتائج التدقيق المالي."
with col2:
    if st.button("⏳ فحص شروط وتنبيهات العقود"):
        quick_prompt = "ما هي فترات التنبيه المعتمدة للعقود قبل انتهائها، وكيف يتم تصنيف درجات الأولوية للمراسلات؟"
with col3:
    if st.button("🔍 استعلام SQL للعقود المنتهية"):
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


