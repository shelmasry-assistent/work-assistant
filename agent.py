import os
import glob
from dotenv import load_dotenv
from google import genai
from google.genai import types

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

def check_api_key():
    if not API_KEY or API_KEY == "ضع_المفتاح_الخاص_بك_هنا":
        print("=" * 60)
        print("تنبيه: لم يتم العثور على مفتاح GEMINI_API_KEY صالح!")
        print("يرجى إنشاء ملف باسم .env ووضع المفتاح داخله:")
        print("GEMINI_API_KEY=AIzaSy...")
        print("=" * 60)
        return False
    return True

def load_knowledge_base(folder_path="knowledge_base"):
    """قراءة كل الملفات الموجودة في مجلد قاعدة المعرفة ودمجها كسياق للـ Agent"""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        return ""
    
    knowledge_texts = []
    supported_extensions = ["*.txt", "*.md", "*.sql", "*.csv", "*.json"]
    
    for ext in supported_extensions:
        files = glob.glob(os.path.join(folder_path, "**", ext), recursive=True)
        for filepath in files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        filename = os.path.basename(filepath)
                        knowledge_texts.append(f"--- [ملف مرجعي: {filename}] ---\n{content}\n")
            except Exception as e:
                print(f"تعذر قراءة الملف {filepath}: {e}")
                
    return "\n\n".join(knowledge_texts)

def main():
    if not check_api_key():
        return

    print("جاري تحميل قاعدة المعرفة الخاصة بعملك...")
    knowledge = load_knowledge_base()
    
    # التعليمات الإرشادية للنظام (System Instructions)
    system_instruction = f"""
أنت مساعد ذكي مخصص وخبير، وظيفتك هي مساعدة المستخدم في جميع تفاصيل وأعباء عمله اليومي.
لديك وصول كامل لقاعدة معرفة عمل المستخدم المرفقة أدناه.

قواعدك الأساسية:
1. استخدم المعلومات الواردة في قاعدة المعرفة أدناه للإجابة بدقة عن أي استفسارات تتعلق بإجراءات العمل، الخطابات، العقود، والأنظمة.
2. إذا سُئلت عن شيء غير موجود في المعرفة المرفقة، يمكنك استخدام ذكائك العام مع توضيح ذلك للمستخدم.
3. التزم بأسلوب مهني وواضح، واستخدم اللغة العربية الفصحى السلسة والمناسبة لبيئة العمل الإدارية والتقنية.
4. ساعد في صياغة الخطابات، التدقيق، تلخيص المعاملات، واقتراح الخطوات التالية.

--- بداية قاعدة المعرفة الخاصة بالمستخدم ---
{knowledge if knowledge else "لا توجد ملفات حالياً في مجلد knowledge_base."}
--- نهاية قاعدة المعرفة ---
"""

    # تهيئة عميل Gemini
    client = genai.Client(api_key=API_KEY)
    
    # إنشاء جلسة محادثة تفاعلية (Chat)
    chat = client.chats.create(
        model="gemini-3.6-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3,
        )
    )

    print("\n" + "=" * 60)
    print(" تم تشغيل المساعد الذكي بنجاح!")
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
