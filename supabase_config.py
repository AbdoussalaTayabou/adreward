# ============================================================
# supabase_config.py — Connexion à la base de données
# Les clés sont lues depuis les variables d'environnement
# configurées sur Render.com (jamais dans le code source).
# ============================================================

import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://bkmambkdvwdfufhgjrvz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJrbWFtYmtkdndkZnVmaGdqcnZ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg0OTQyMzMsImV4cCI6MjA5NDA3MDIzM30.4-zNu5RPHyHaP4WbId08btvrbPSzqgDzpYN0B-fApnQ")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)