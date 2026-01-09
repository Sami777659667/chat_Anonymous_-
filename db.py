import logging
import certifi
import time
from pymongo import MongoClient
from config import Config
import dns.resolver

logger = logging.getLogger(__name__)

# حل مشكلة DNS في بيئات الأندرويد (Termux/Alif)
try:
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']
except Exception as e:
    logger.warning(f"⚠️ DNS Setup: {e}")

class DatabaseManager:
    def __init__(self):
        self.uri = Config.MONGO_URL
        self.db = None
        self._connect()

    def _connect(self):
        """الاتصال بـ MongoDB Atlas"""
        try:
            self.client = MongoClient(
                self.uri, 
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000
            )
            self.client.admin.command('ping')
            self.db = self.client['TelegramBot']
            logger.info("✅ تم الاتصال بـ MongoDB بنجاح!")
        except Exception as e:
            logger.error(f"❌ فشل اتصال القاعدة: {e}")
            self.db = None

    def get_user(self, user_id):
        """جلب بيانات المستخدم"""
        if self.db is not None:
            return self.db.users.find_one({"user_id": user_id}) or {}
        return {}

    def add_user(self, user_id, name, username):
        """إضافة أو تحديث بيانات المستخدم عند الضغط على start"""
        if self.db is not None:
            try:
                self.db.users.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "first_name": name,
                            "username": username
                        },
                        "$setOnInsert": {
                            "points": 10,
                            "nickname": "نخبة ✨",
                            "gender": "غير محدد",
                            "age": "غير محدد",
                            "country": "غير محدد",
                            "referred_count": 0,
                            "join_date": time.time()
                        }
                    },
                    upsert=True
                )
            except Exception as e:
                logger.error(f"❌ Error in add_user: {e}")

    def update_points(self, user_id, amount):
        """تحديث رصيد الفلفل (زيادة أو نقصان)"""
        if self.db is not None:
            self.db.users.update_one(
                {"user_id": user_id},
                {"$inc": {"points": amount}}
            )

    def get_points(self, user_id):
        """جلب رصيد الفلفل فقط"""
        user = self.get_user(user_id)
        return user.get("points", 0)

    def update_user_data(self, user_id, field, value):
        """تحديث حقل معين في بيانات المستخدم (اللقب، الدولة، إلخ)"""
        if self.db is not None:
            self.db.users.update_one(
                {"user_id": user_id},
                {"$set": {field: value}}
            )

# إنشاء نسخة واحدة ليتم استدعاؤها في كل مكان
db = DatabaseManager()
