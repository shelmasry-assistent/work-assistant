import os
import glob
import json
import zipfile
import xml.etree.ElementTree as ET
import oracledb
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

ORACLE_HOST = os.getenv("ORACLE_HOST", "192.168.200.10")
ORACLE_PORT = os.getenv("ORACLE_PORT", "1521")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE", "XEPDB1")
ORACLE_USER = os.getenv("ORACLE_USER", "CONTRACTS_APP")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "imc#wis")

def check_api_key():
    if not API_KEY or API_KEY == "ضع_المفتاح_الخاص_بك_هنا":
        print("=" * 60)
        print("تنبيه: لم يتم العثور على مفتاح GEMINI_API_KEY صالح!")
        print("يرجى إنشاء ملف باسم .env ووضع المفتاح داخله:")
        print("GEMINI_API_KEY=AIzaSy...")
        print("=" * 60)
        return False
    return True

def sync_live_oracle():
    """جلب البيانات الحية المباشرة من قاعدة بيانات أوراكل بدون أي بيانات ثنائية ثابتة"""
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
                STATUS AS "status"
            FROM APP_CONTRACTS 
            ORDER BY CONTRACT_ID DESC
        """)
        cols = [col[0] for col in cursor.description]
        contracts = [dict(zip(cols, row)) for row in cursor.fetchall()]
        connection.close()
        
        target_path = os.path.join("knowledge_base", "oracle_contracts_and_assets.json")
        with open(target_path, "w", encoding="utf-8") as dst:
            json.dump({"contracts": contracts}, dst, ensure_ascii=False, indent=2)
        print(f"✅ تم جلب {len(contracts)} عقد حي مباشرة من قاعدة بيانات أوراكل ({ORACLE_HOST})")
    except Exception as e:
        print(f"⚠️ تعذر الاتصال المباشر بأوراكل: {e}")

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
        return f"[خطأ قراءة Word: {e}]"

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
    except Exception as e:
        return f"[خطأ قراءة PDF: {e}]"

def extract_excel_text(filepath):
    try:
        import pandas as pd
        excel_file = pd.ExcelFile(filepath)
        sheet_texts = []
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            sheet_texts.append(f"--- ورقة عمل: {sheet_name} ---\n" + df.to_string(index=False))
        return "\n".join(sheet_texts)
    except Exception as e:
        return f"[خطأ قراءة Excel: {e}]"

def load_knowledge_base(folder_path="knowledge_base"):
    sync_live_oracle()
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        return ""
    
    knowledge_texts = []
    supported_extensions = ["*.txt", "*.md", "*.sql", "*.csv", "*.json", "*.docx", "*.pdf", "*.xlsx", "*.xls"]
    
    for ext in supported_extensions:
        files = glob.glob(os.path.join(folder_path, "**", ext), recursive=True)
        for filepath in files:
            filename = os.path.basename(filepath)
            ext_name = os.path.splitext(filename)[1].lower()
            content = ""
            
            try:
                if ext_name == ".docx":
                    content = extract_docx_text(filepath)
                elif ext_name == ".pdf":
                    content = extract_pdf_text(filepath)
                elif ext_name in [".xlsx", ".xls"]:
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
                print(f"تعذر قراءة الملف {filepath}: {e}")
                
    return "\n\n".join(knowledge_texts)

def main():
    if not check_api_key():
        return

    print("جاري الاتصال المباشر بأوراكل وتحميل البيانات الحية...")
    knowledge = load_knowledge_base()
    
    system_instruction = f"""
أنت مساعد ذكي مخصص وخبير، وظيفتك هي مساعدة المستخدم في جميع تفاصيل وأعباء عمله اليومية (الخطابات، العقود، المواعيد النهائية، وقواعد بيانات أوراكل).
لديك وصول كامل ومباشر لقاعدة بيانات أوراكل الحية (192.168.200.10:1521/XEPDB1).

قواعدك الأساسية:
1. استند دائماً إلى البيانات الحية المجلوبة المباشرة من أوراكل (جدول APP_CONTRACTS) بدون أي تعديل.
2. إذا سُئلت عن شيء غير موجود في المعرفة المرفقة، يمكنك استخدام ذكائك العام مع توضيح ذلك للمستخدم.
3. التزم بأسلوب مهني وواضح، واستخدم اللغة العربية الفصحى السلسة والمناسبة لبيئة العمل الإدارية والتقنية.
4. ساعد في صياغة الخطابات، التدقيق، تلخيص المعاملات، واقتراح الخطوات التالية.

--- بداية قاعدة المعرفة الخاصة بالمستخدم ---
{knowledge if knowledge else "لا توجد ملفات حالياً في مجلد knowledge_base."}
--- نهاية قاعدة المعرفة ---
"""

    client = genai.Client(api_key=API_KEY)
    model_name = "gemini-2.5-flash"
    
    try:
        chat = client.chats.create(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
            )
        )
    except Exception:
        model_name = "gemini-1.5-flash"
        chat = client.chats.create(
            model=model_name,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
            )
        )

    print("\n" + "=" * 60)
    print(" تم تشغيل المساعد الذكي بنجاح والمربوط حياً بقاعدة بيانات أوراكل!")
    print(f" النموذج النشط: {model_name}")
    print(" يمكنك الآن سؤاله عن أي شيء في عملك، أو طلب صياغة خطابات وعقود.")
    print(" للخروج اكتب: 'خروج' أو 'exit'")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("أنت: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["خروج", "exit", "quit"]:
                print("مع السلامة! بالتوفيق في عملك.")
                break

            response = chat.send_message(user_input)
            print(f"\nالمساعد:\n{response.text}\n")
            print("-" * 50)
            
        except KeyboardInterrupt:
            print("\nتم إيقاف البرنامج.")
            break
        except Exception as err:
            print(f"\nحدث خطأ: {err}\n")

if __name__ == "__main__":
    main()
