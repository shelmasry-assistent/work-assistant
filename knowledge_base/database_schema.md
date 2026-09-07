# هيكل قاعدة بيانات أوراكل (Oracle Database Schema)

هذا الملف يوضح الجداول والعلاقات الأساسية لتمكين المساعد من فهم الاستعلامات وصياغة أكواد SQL بدقة:

## 1. جدول العقود والمواعيد (CONTRACTS)
- `CONTRACT_ID` (NUMBER - PK): المعرف الفريد للعقد.
- `CONTRACT_NUMBER` (VARCHAR2): رقم العقد أو المرجع.
- `TITLE` (VARCHAR2): عنوان العقد أو موضوع القرار.
- `TYPE_ID` (NUMBER - FK -> CONTRACT_TYPES): نوع العقد.
- `PARTY_NAME` (VARCHAR2): اسم الطرف الآخر / الشركة / الجهة المتعاقدة.
- `DEPARTMENT_ID` (NUMBER - FK -> DEPARTMENTS): الإدارة المسؤولة.
- `ASSIGNED_USER_ID` (NUMBER - FK -> USERS): الموظف المسؤول عن المتابعة.
- `START_DATE` (DATE): تاريخ بداية العقد.
- `EXPIRY_DATE` (DATE): تاريخ انتهاء العقد.
- `NOTICE_DAYS_1` (NUMBER, افتراضي 60): أيام التنبيه الأول.
- `NOTICE_DAYS_2` (NUMBER, افتراضي 30): أيام التنبيه الثاني.
- `NOTICE_DAYS_3` (NUMBER, افتراضي 7): أيام التنبيه الثالث.
- `STATUS` (VARCHAR2): الحالة (ACTIVE, EXPIRED, RENEWED, إلخ).
- `CONTRACT_VALUE` (NUMBER): قيمة العقد المالية.
- `CURRENCY` (VARCHAR2): العملة (مثل EGP, USD, SAR).
- `AUTO_RENEWAL` (CHAR 'Y'/'N'): هل يجدد تلقائياً.

## 2. جدول أنواع العقود (CONTRACT_TYPES)
- `TYPE_ID` (NUMBER - PK)
- `TYPE_CODE` (VARCHAR2: CONTRACT, LICENSE, DECISION, LEASE, INSURANCE)
- `TYPE_NAME` (VARCHAR2: الاسم بالعربية)

## 3. جداول الخطابات والمراسلات (LETTERS)
- الخطابات الواردة والصادرة ترتبط بإجراءات حزمة `LETTERS_PKG`:
  - `generate_letter_number(p_letter_type)`: توليد رقم الخطاب (IN/OUT).
  - `register_incoming(...)`: تسجيل وارد جديد.
  - `route_letter(...)`: إحالة الخطاب للموظف أو الإدارة المعنية.
- حقول المراسلات الأساسية:
  - تاريخ الاستلام/التصدير.
  - الجهة المراسلة (CORRESPONDENT).
  - الموضوع والأولوية (NORMAL, URGENT, TOP_URGENT).
  - درجة السرية (PUBLIC, CONFIDENTIAL, TOP_SECRET).
