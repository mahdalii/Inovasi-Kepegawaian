import os

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_UPLOAD_MB = 4
STAFF_PASSWORD = os.environ.get("STAFF_PASSWORD", "admin123")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
STORAGE_BUCKET = "berkas"