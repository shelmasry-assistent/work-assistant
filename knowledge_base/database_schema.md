# هيكل قاعدة بيانات أوراكل الحقيقية للأنظمة والشبكات (Oracle Production Schema)

هذا التوثيق يمثل الهيكل الحقيقي والكامل لجداول وقواعد بيانات أوراكل المعتمدة لديك، والتي استخرجتها مباشرة من Oracle SQL Developer:

---

## 1. جدول العقود الرئيسي (`APP_CONTRACTS`)
يحوي جميع بيانات العقود والتراخيص والقرارات الإدارية.
- `CONTRACT_ID` (NUMBER - PK): المعرف الفريد للعقد.
- `CONTRACT_NUMBER` (VARCHAR2(100)): رقم العقد أو المرجع.
- `TITLE` (VARCHAR2(300)): عنوان أو موضوع العقد.
- `TYPE_NAME` (VARCHAR2(150)): نوع العقد (عقد توريد، صيانة، رخصة، إلخ).
- `PARTY_NAME` (VARCHAR2(200)): اسم الشركة أو الجهة المتعاقدة.
- `DEPARTMENT_NAME` (VARCHAR2(150)): الإدارة المسؤولة.
- `ASSIGNED_TO` (VARCHAR2(150)): الموظف/المسؤول عن المتابعة.
- `CONTRACT_VALUE` (NUMBER(15,2)): قيمة العقد المالية.
- `START_DATE` (DATE): تاريخ بداية العقد.
- `EXPIRY_DATE` (DATE): تاريخ انتهاء العقد.
- `NOTICE_DAYS_1` (NUMBER(4,0)): أيام التنبيه الأول (60 يوماً).
- `NOTICE_DAYS_2` (NUMBER(4,0)): أيام التنبيه الثاني (30 يوماً).
- `NOTICE_DAYS_3` (NUMBER(4,0)): أيام التنبيه الثالث (7 أيام).
- `STATUS` (VARCHAR2(50)): حالة العقد (ساري، أوشك على الانتهاء، منتهي، إلخ).
- `AUTO_RENEW` (CHAR(1)): تجديد تلقائي ('Y'/'N').
- `ATTACHMENT_URL` (VARCHAR2(500)): رابط أو اسم مرفق العقد.
- `NOTES` (VARCHAR2(4000)): ملاحظات تفصيلية عن العقد.
- `CREATED_AT` / `UPDATED_AT` (TIMESTAMP(6)): تواريخ الإنشاء والتحديث.

---

## 2. جدول تجديدات العقود (`APP_CONTRACT_RENEWALS`)
يسجل تاريخ وتفاصيل كل تجديد يطرأ على العقود.
- `RENEWAL_ID` (NUMBER - PK): المعرف الفريد للتجديد.
- `CONTRACT_NUMBER` (VARCHAR2(100)): رقم العقد المجدد.
- `CONTRACT_TITLE` (VARCHAR2(300)): عنوان العقد.
- `OLD_EXPIRY_DATE` (DATE): تاريخ الانتهاء القديم.
- `NEW_EXPIRY_DATE` (DATE): تاريخ الانتهاء الجديد بعد التجديد.
- `OLD_VALUE` (NUMBER(15,2)): القيمة الماليّة القديمة.
- `NEW_VALUE` (NUMBER(15,2)): القيمة المالية الجديدة بعد التعديل.
- `RENEWAL_DATE` (TIMESTAMP(6)): تاريخ ووقت إجراء التجديد.
- `RENEWED_BY` (VARCHAR2(150)): الموظف الذي قام بالتجديد.
- `ATTACHMENT_FILE` (VARCHAR2(255)): مرفق قرار التجديد.
- `RENEWAL_NOTES` (VARCHAR2(1000)): ملاحظات التجديد.

---

## 3. جدول إجراءات وتغييرات العقود (`APP_CONTRACT_ACTIONS`)
سجل الحركة والأنشطة المتخذة على العقد (Audit Trail).
- `ACTION_ID` (NUMBER - PK)
- `CONTRACT_ID` (NUMBER - FK -> APP_CONTRACTS.CONTRACT_ID)
- `ACTION_TYPE` (VARCHAR2(50)): نوع الإجراء (تعديل، تمديد، إيقاف، مراجعة).
- `ACTION_DATE` (DATE): تاريخ الإجراء.
- `DETAILS` (VARCHAR2(4000)): تفاصيل الإجراء.
- `PERFORMED_BY` (VARCHAR2(150)): من قام بالإجراء.
- `NEW_EXPIRY_DATE` (DATE): تاريخ الانتهاء الجديد إن وجد.

---

## 4. جدول الأصول وماكينات التصوير (`APP_ASSETS` / `C_ASSETS`)
سجل الأصول والأجهزة وماكينات التصوير الموزعة في الإدارات.
- `ASSET_ID` (NUMBER - PK)
- `SERIAL_NUMBER` (VARCHAR2(100)): السيريال نمبر الفريد للجهاز.
- `ASSET_NAME` (VARCHAR2(200)): اسم الماكينة/الطابعة/الجهاز.
- `ASSET_TYPE` (VARCHAR2(100)): نوع الأصل (ماكينة تصوير، طابعة، سيرفر).
- `CONTRACT_NUMBER` (VARCHAR2(100)): رقم عقد التوريد أو الصيانة المربوط به.
- `CONTRACT_TITLE` (VARCHAR2(300)): عنوان العقد المربوط.
- `DEPARTMENT_NAME` (VARCHAR2(150)): الإدارة الموجود بها الجهاز.
- `LOCATION_DETAILS` (VARCHAR2(200)): تفاصيل موقع الجهاز (الدور/الغرفة).
- `STATUS` (VARCHAR2(50)): حالة الجهاز (تعمل، تحت الصيانة، عاطلة).
- `PURCHASE_DATE` (DATE): تاريخ الشراء.
- `NOTES` (VARCHAR2(1000)): ملاحظات إضافية.

---

## 5. جدول طلبات وسجلات صيانة ماكينات التصوير والأصول (`APP_MAINTENANCE_LOGS`)
- `MAINTENANCE_ID` (NUMBER - PK)
- `SERIAL_NUMBER` (VARCHAR2(100)): السيريال نمبر للماكينة.
- `MAINTENANCE_TYPE` (VARCHAR2(100)): نوع الصيانة (دورية، عاجلة، أحبار، قطع غيار).
- `MAINTENANCE_DATE` (DATE): تاريخ تنفيذ الصيانة.
- `TECHNICIAN_NAME` (VARCHAR2(150)): اسم المهندس/الفني أو شركة الصيانة.
- `PARTS_REPLACED` (VARCHAR2(500)): قطع الغيار المستبدلة.
- `COST` (NUMBER(12,2)): التكلفة المالية للصيانة.
- `NEXT_SERVICE_DATE` (DATE): موعد الصيانة القادمة المستهدف.
- `DETAILS` (VARCHAR2(1000)): تفاصيل أعمال الصيانة.

---

## 6. جداول متابعة طلبات صيانة الأجهزة والماكينات (`MAINT_MACHINES`, `MAINT_REQUESTS`, `MAINT_SCHEDULE`)
- **`MAINT_MACHINES`**: كود الماكينة (`MACHINE_CODE`)، الماركة (`BRAND`)، الموديل (`MODEL`)، الرقم التسلسلي (`SERIAL_NO`)، الموقع والنشاط.
- **`MAINT_REQUESTS`**: بلاغات وأعطال الماكينات (`REQUEST_ID`, `MACHINE_ID` -> `MAINT_MACHINES`, `PROBLEM`, `ACTION_TAKEN`, `PARTS`, `STATUS`, `CLOSE_DATE`).
- **`MAINT_SCHEDULE`**: جدولة زيارات الصيانة الوقائية والدورية (`DUE_DATE`, `DONE_DATE`, `STATUS`).

---

## 7. جداول الوحدات والمستخدمين والأنواع (`APP_DEPARTMENTS`, `APP_USERS`, `APP_CONTRACT_TYPES`)
- **`APP_DEPARTMENTS`**: دليل الإدارات والقطاعات (`DEPARTMENT_NAME`).
- **`APP_USERS`**: اسم المستخدم، الاسم الكامل، الإدارة، الدور (`ROLE`).
- **`APP_CONTRACT_TYPES`**: أنواع العقود (`TYPE_NAME`, `DESCRIPTION`).
