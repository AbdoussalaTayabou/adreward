# ============================================================
# api.py — Toutes les fonctions qui touchent la base de données
# ============================================================

import hashlib
from supabase_config import supabase


def chiffrer_mot_de_passe(mot_de_passe):
    return hashlib.sha256(mot_de_passe.encode()).hexdigest()


def creer_utilisateur(nom, email, mot_de_passe):
    try:
        mot_de_passe_chiffre = chiffrer_mot_de_passe(mot_de_passe)
        resultat = supabase.table("utilisateurs").insert({
            "nom": nom,
            "email": email,
            "mot_de_passe": mot_de_passe_chiffre
        }).execute()
        return resultat.data[0] if resultat.data else None
    except Exception as e:
        print(f"Erreur création utilisateur: {e}")
        return None


def connecter_utilisateur(email, mot_de_passe):
    mot_de_passe_chiffre = chiffrer_mot_de_passe(mot_de_passe)
    resultat = supabase.table("utilisateurs") \
        .select("*") \
        .eq("email", email) \
        .eq("mot_de_passe", mot_de_passe_chiffre) \
        .execute()
    return resultat.data[0] if resultat.data else None


def get_utilisateur(utilisateur_id):
    try:
        resultat = supabase.table("utilisateurs") \
            .select("*") \
            .eq("id", utilisateur_id) \
            .execute()
        return resultat.data[0] if resultat.data else None
    except Exception as e:
        print(f"Erreur get_utilisateur: {e}")
        return None


def transaction_existe(transaction_id):
    try:
        resultat = supabase.table("transactions") \
            .select("id") \
            .eq("transaction_id", transaction_id) \
            .execute()
        return len(resultat.data) > 0
    except Exception as e:
        print(f"Erreur transaction_existe: {e}")
        return False


def crediter_solde(utilisateur_id, montant_fcfa, transaction_id, source="cpx"):
    if transaction_existe(transaction_id):
        print(f"Transaction {transaction_id} déjà traitée. Ignorée.")
        return False

    try:
        utilisateur = get_utilisateur(utilisateur_id)
        if not utilisateur:
            return False

        nouveau_solde = utilisateur["solde"] + montant_fcfa

        supabase.table("utilisateurs") \
            .update({"solde": nouveau_solde}) \
            .eq("id", utilisateur_id) \
            .execute()

        supabase.table("transactions").insert({
            "utilisateur_id": utilisateur_id,
            "transaction_id": transaction_id,
            "montant_fcfa": montant_fcfa,
            "source": source
        }).execute()

        print(f"✅ Crédité {montant_fcfa} FCFA à {utilisateur_id}. Nouveau solde : {nouveau_solde} FCFA")
        return True

    except Exception as e:
        print(f"Erreur crediter_solde: {e}")
        return False


def get_transactions(utilisateur_id, limite=50):
    try:
        resultat = supabase.table("transactions") \
            .select("id, montant_fcfa, source, transaction_id, created_at") \
            .eq("utilisateur_id", utilisateur_id) \
            .order("created_at", desc=True) \
            .limit(limite) \
            .execute()
        return resultat.data if resultat.data else []
    except Exception as e:
        print(f"Erreur get_transactions: {e}")
        return []


def retrait_en_attente_existe(utilisateur_id):
    try:
        resultat = supabase.table("retraits") \
            .select("id") \
            .eq("utilisateur_id", utilisateur_id) \
            .eq("statut", "en_attente") \
            .execute()
        return len(resultat.data) > 0
    except Exception as e:
        print(f"Erreur retrait_en_attente_existe: {e}")
        return False


def creer_retrait(utilisateur_id, montant_fcfa, operateur, numero_telephone):
    if retrait_en_attente_existe(utilisateur_id):
        return None, "Tu as déjà une demande en cours. Attends qu'elle soit traitée."

    try:
        utilisateur = get_utilisateur(utilisateur_id)
        if not utilisateur:
            return None, "Utilisateur introuvable."

        if utilisateur["solde"] < montant_fcfa:
            return None, "Solde insuffisant."

        if montant_fcfa < 500:
            return None, "Le montant minimum de retrait est 500 FCFA."

        nouveau_solde = utilisateur["solde"] - montant_fcfa
        supabase.table("utilisateurs") \
            .update({"solde": nouveau_solde}) \
            .eq("id", utilisateur_id) \
            .execute()

        supabase.table("retraits").insert({
            "utilisateur_id": utilisateur_id,
            "montant_fcfa": montant_fcfa,
            "operateur": operateur,
            "numero_telephone": numero_telephone,
            "statut": "en_attente"
        }).execute()

        print(f"✅ Retrait demandé : {montant_fcfa} FCFA → {operateur} {numero_telephone}")
        return "ok", None

    except Exception as e:
        print(f"Erreur creer_retrait: {e}")
        return None, "Une erreur est survenue. Réessaie plus tard."


def get_retraits(utilisateur_id, limite=20):
    try:
        resultat = supabase.table("retraits") \
            .select("id, montant_fcfa, operateur, numero_telephone, statut, created_at") \
            .eq("utilisateur_id", utilisateur_id) \
            .order("created_at", desc=True) \
            .limit(limite) \
            .execute()
        return resultat.data if resultat.data else []
    except Exception as e:
        print(f"Erreur get_retraits: {e}")
        return []


# ============================================================
# FONCTIONS ADMIN
# ============================================================

def admin_get_retraits_en_attente():
    try:
        resultat = supabase.table("retraits") \
            .select("id, montant_fcfa, operateur, numero_telephone, statut, created_at, utilisateur_id") \
            .eq("statut", "en_attente") \
            .order("created_at", desc=False) \
            .execute()
        retraits = resultat.data if resultat.data else []
        for r in retraits:
            utilisateur = get_utilisateur(r["utilisateur_id"])
            r["utilisateur_nom"]   = utilisateur["nom"]   if utilisateur else "—"
            r["utilisateur_email"] = utilisateur["email"] if utilisateur else "—"
        return retraits
    except Exception as e:
        print(f"Erreur admin_get_retraits_en_attente: {e}")
        return []


def admin_valider_retrait(retrait_id):
    try:
        supabase.table("retraits") \
            .update({"statut": "validé"}) \
            .eq("id", retrait_id) \
            .execute()
        return True
    except Exception as e:
        print(f"Erreur admin_valider_retrait: {e}")
        return False


def admin_refuser_retrait(retrait_id):
    try:
        resultat = supabase.table("retraits") \
            .select("utilisateur_id, montant_fcfa") \
            .eq("id", retrait_id) \
            .execute()
        if not resultat.data:
            return False
        retrait = resultat.data[0]

        utilisateur = get_utilisateur(retrait["utilisateur_id"])
        if utilisateur:
            nouveau_solde = utilisateur["solde"] + retrait["montant_fcfa"]
            supabase.table("utilisateurs") \
                .update({"solde": nouveau_solde}) \
                .eq("id", retrait["utilisateur_id"]) \
                .execute()

        supabase.table("retraits") \
            .update({"statut": "refusé"}) \
            .eq("id", retrait_id) \
            .execute()

        print(f"✅ Retrait {retrait_id} refusé. {retrait['montant_fcfa']} FCFA remboursés.")
        return True
    except Exception as e:
        print(f"Erreur admin_refuser_retrait: {e}")
        return False


def admin_get_stats():
    try:
        res_users = supabase.table("utilisateurs").select("id, solde").execute()
        utilisateurs    = res_users.data if res_users.data else []
        nb_utilisateurs = len(utilisateurs)
        total_soldes    = sum(u["solde"] for u in utilisateurs)

        res_tx = supabase.table("transactions").select("montant_fcfa").execute()
        transactions    = res_tx.data if res_tx.data else []
        nb_transactions = len(transactions)
        total_distribue = sum(t["montant_fcfa"] for t in transactions)

        res_ret = supabase.table("retraits").select("montant_fcfa, statut").execute()
        retraits        = res_ret.data if res_ret.data else []
        nb_en_attente   = sum(1 for r in retraits if r["statut"] == "en_attente")
        total_retire    = sum(r["montant_fcfa"] for r in retraits if r["statut"] == "validé")
        montant_attente = sum(r["montant_fcfa"] for r in retraits if r["statut"] == "en_attente")

        return {
            "nb_utilisateurs":  nb_utilisateurs,
            "total_soldes":     total_soldes,
            "nb_transactions":  nb_transactions,
            "total_distribue":  total_distribue,
            "nb_en_attente":    nb_en_attente,
            "total_retire":     total_retire,
            "montant_attente":  montant_attente,
        }
    except Exception as e:
        print(f"Erreur admin_get_stats: {e}")
        return {}


def admin_get_tous_retraits(limite=100):
    try:
        resultat = supabase.table("retraits") \
            .select("id, montant_fcfa, operateur, numero_telephone, statut, created_at, utilisateur_id") \
            .order("created_at", desc=True) \
            .limit(limite) \
            .execute()
        retraits = resultat.data if resultat.data else []
        for r in retraits:
            utilisateur = get_utilisateur(r["utilisateur_id"])
            r["utilisateur_nom"]   = utilisateur["nom"]   if utilisateur else "—"
            r["utilisateur_email"] = utilisateur["email"] if utilisateur else "—"
        return retraits
    except Exception as e:
        print(f"Erreur admin_get_tous_retraits: {e}")
        return []