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
    # ============================================================
    # Vérifie si l'utilisateur a déjà une demande de retrait
    # en attente. On interdit d'en soumettre deux en même temps.
    # ============================================================
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
    # ============================================================
    # Crée une demande de retrait.
    #
    # Étapes :
    #   1. Vérifie qu'il n'y a pas déjà une demande en attente
    #   2. Vérifie que le solde est suffisant
    #   3. Déduit le montant du solde immédiatement
    #      (l'utilisateur ne peut pas dépenser cet argent
    #       pendant que la demande est en cours)
    #   4. Enregistre la demande dans la table "retraits"
    #
    # Retourne : ("ok", None) en cas de succès
    #         ou (None, "message d'erreur") en cas d'échec
    # ============================================================

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

        # Déduit le montant du solde immédiatement
        nouveau_solde = utilisateur["solde"] - montant_fcfa
        supabase.table("utilisateurs") \
            .update({"solde": nouveau_solde}) \
            .eq("id", utilisateur_id) \
            .execute()

        # Enregistre la demande
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
    # ============================================================
    # Récupère les dernières demandes de retrait d'un utilisateur.
    # ============================================================
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
# FONCTIONS ADMIN — À ajouter à la fin de api.py
# ============================================================

def admin_get_retraits_en_attente():
    """Récupère tous les retraits en attente avec les infos utilisateur."""
    try:
        resultat = supabase.table("retraits") \
            .select("id, montant_fcfa, operateur, numero_telephone, statut, created_at, utilisateur_id") \
            .eq("statut", "en_attente") \
            .order("created_at", desc=False) \
            .execute()
        # On enrichit chaque retrait avec le nom et l'email de l'utilisateur
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
    """Passe le statut d'un retrait à 'validé'."""
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
    """
    Passe le statut d'un retrait à 'refusé' ET
    rembourse le montant dans le solde de l'utilisateur.
    """
    try:
        # 1. Récupère les infos du retrait
        resultat = supabase.table("retraits") \
            .select("utilisateur_id, montant_fcfa") \
            .eq("id", retrait_id) \
            .execute()
        if not resultat.data:
            return False
        retrait = resultat.data[0]

        # 2. Rembourse le solde de l'utilisateur
        utilisateur = get_utilisateur(retrait["utilisateur_id"])
        if utilisateur:
            nouveau_solde = utilisateur["solde"] + retrait["montant_fcfa"]
            supabase.table("utilisateurs") \
                .update({"solde": nouveau_solde}) \
                .eq("id", retrait["utilisateur_id"]) \
                .execute()

        # 3. Met à jour le statut
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
    """Calcule les statistiques globales pour le dashboard admin."""
    try:
        # Nombre d'utilisateurs
        res_users = supabase.table("utilisateurs").select("id, solde").execute()
        utilisateurs = res_users.data if res_users.data else []
        nb_utilisateurs  = len(utilisateurs)
        total_soldes     = sum(u["solde"] for u in utilisateurs)

        # Transactions
        res_tx = supabase.table("transactions").select("montant_fcfa").execute()
        transactions     = res_tx.data if res_tx.data else []
        nb_transactions  = len(transactions)
        total_distribue  = sum(t["montant_fcfa"] for t in transactions)

        # Retraits
        res_ret = supabase.table("retraits").select("montant_fcfa, statut").execute()
        retraits         = res_ret.data if res_ret.data else []
        nb_en_attente    = sum(1 for r in retraits if r["statut"] == "en_attente")
        total_retire     = sum(r["montant_fcfa"] for r in retraits if r["statut"] == "validé")
        montant_attente  = sum(r["montant_fcfa"] for r in retraits if r["statut"] == "en_attente")

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
    """Récupère tous les retraits (toutes statuts) pour l'historique admin."""
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