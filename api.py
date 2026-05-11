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
    # ============================================================
    # Vérifie si une transaction a déjà été traitée.
    # C'est une sécurité anti-doublon : si CPX envoie deux fois
    # le même postback (ça peut arriver), on ne crédite qu'une
    # seule fois. On vérifie dans la table "transactions"
    # si l'identifiant unique de la transaction existe déjà.
    # ============================================================
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
    # ============================================================
    # Crédite le solde d'un utilisateur après une offre complétée.
    # ============================================================

    # Étape 1 : anti-doublon
    if transaction_existe(transaction_id):
        print(f"Transaction {transaction_id} déjà traitée. Ignorée.")
        return False

    try:
        # Étape 2 : récupère le solde actuel
        utilisateur = get_utilisateur(utilisateur_id)
        if not utilisateur:
            print(f"Utilisateur {utilisateur_id} introuvable.")
            return False

        solde_actuel = utilisateur["solde"]
        nouveau_solde = solde_actuel + montant_fcfa

        # Étape 3 : met à jour le solde
        supabase.table("utilisateurs") \
            .update({"solde": nouveau_solde}) \
            .eq("id", utilisateur_id) \
            .execute()

        # Étape 4 : enregistre la transaction
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
    # ============================================================
    # Récupère les dernières transactions d'un utilisateur.
    #
    # Paramètres :
    #   utilisateur_id : l'ID de l'utilisateur
    #   limite         : nombre max de transactions à retourner
    #                    (par défaut 50, les plus récentes d'abord)
    #
    # Retourne une liste de dicts, ex :
    # [
    #   {
    #     "id": 1,
    #     "montant_fcfa": 98,
    #     "source": "cpx",
    #     "transaction_id": "TX999",
    #     "created_at": "2025-01-15T14:32:00"
    #   },
    #   ...
    # ]
    # ============================================================
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