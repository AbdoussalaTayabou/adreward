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