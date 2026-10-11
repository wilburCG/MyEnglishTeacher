import os
import sys

# 必须在任何 app.* 导入前完成：测试一律走临时 sqlite，不碰 Postgres
os.environ["DATABASE_URL"] = "sqlite:///./test_met.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["MEDIA_DIR"] = "/tmp/met-test-media"

if os.path.exists("./test_met.db"):
    os.remove("./test_met.db")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
