# ============================================================
# app.py — Fichier principal
# ============================================================

import hashlib
from flask import Flask, render_template, request, redirect, url_for, session
from api import (
    creer_utilisateur, connecter_utilisateur, get_utilisateur,
    crediter_solde, get_transactions,
    creer_retrait, get_retraits, admin_get_retraits_en_attente, admin_valider_retrait,
    admin_refuser_retrait, admin_get_stats, admin_get_tous_retraits
)

app = Flask(__name__)
app.secret_key = "adreward-secret-key-changer-en-production"

CPX_APP_ID       = "32995"
CPX_SECRET       = "SJOAjIyqrNKd8VsJBhNg4EcTTy23C9pi"
TAUX_FCFA        = 563
PART_UTILISATEUR = 0.35

# Opérateurs Mobile Money disponibles
OPERATEURS = ["Orange Money", "Moov Money", "Airtel Money"]


@app.route("/")
def accueil():
    if "utilisateur_id" in session:
        return redirect(url_for("tableau_de_bord"))
    return redirect(url_for("connexion"))


@app.route("/inscription", methods=["GET", "POST"])
def inscription():
    erreur = None
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        email = request.form.get("email", "").strip()
        mot_de_passe = request.form.get("mot_de_passe", "").strip()

        if not nom or not email or not mot_de_passe:
            erreur = "Tous les champs sont obligatoires."
        elif len(mot_de_passe) < 6:
            erreur = "Le mot de passe doit faire au moins 6 caractères."
        else:
            utilisateur = creer_utilisateur(nom, email, mot_de_passe)
            if utilisateur:
                session["utilisateur_id"] = utilisateur["id"]
                session["utilisateur_nom"] = utilisateur["nom"]
                return redirect(url_for("tableau_de_bord"))
            else:
                erreur = "Cet email est déjà utilisé."

    return render_template("inscription.html", erreur=erreur)


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    erreur = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        mot_de_passe = request.form.get("mot_de_passe", "").strip()
        utilisateur = connecter_utilisateur(email, mot_de_passe)

        if utilisateur:
            session["utilisateur_id"] = utilisateur["id"]
            session["utilisateur_nom"] = utilisateur["nom"]
            return redirect(url_for("tableau_de_bord"))
        else:
            erreur = "Email ou mot de passe incorrect."

    return render_template("connexion.html", erreur=erreur)


@app.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("connexion"))


@app.route("/tableau-de-bord")
def tableau_de_bord():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    utilisateur = get_utilisateur(session["utilisateur_id"])
    if not utilisateur:
        session.clear()
        return redirect(url_for("connexion"))

    return render_template("tableau_de_bord.html", utilisateur=utilisateur)


@app.route("/offres")
def offres():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    utilisateur = get_utilisateur(session["utilisateur_id"])
    if not utilisateur:
        session.clear()
        return redirect(url_for("connexion"))

    cpx_url = (
        f"https://offers.cpx-research.com/index.php"
        f"?app_id={CPX_APP_ID}"
        f"&ext_user_id={utilisateur['id']}"
        f"&email={utilisateur['email']}"
        f"&username={utilisateur['nom']}"
        f"&subid_1=adreward"
    )

    return render_template("offres.html", utilisateur=utilisateur, cpx_url=cpx_url)


@app.route("/historique")
def historique():
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    utilisateur = get_utilisateur(session["utilisateur_id"])
    if not utilisateur:
        session.clear()
        return redirect(url_for("connexion"))

    transactions = get_transactions(session["utilisateur_id"])
    return render_template("historique.html", utilisateur=utilisateur, transactions=transactions)


@app.route("/retrait", methods=["GET", "POST"])
def retrait():
    # ============================================================
    # Page de demande de retrait.
    #
    # GET  → affiche le formulaire + l'historique des retraits
    # POST → traite la demande :
    #   1. Valide les champs du formulaire
    #   2. Appelle creer_retrait() qui déduit le solde
    #      et enregistre la demande
    #   3. Redirige vers le tableau de bord avec un message
    #      de confirmation, ou réaffiche le formulaire avec
    #      un message d'erreur
    # ============================================================
    if "utilisateur_id" not in session:
        return redirect(url_for("connexion"))

    utilisateur = get_utilisateur(session["utilisateur_id"])
    if not utilisateur:
        session.clear()
        return redirect(url_for("connexion"))

    erreur = None
    succes = None

    if request.method == "POST":
        operateur        = request.form.get("operateur", "").strip()
        numero_telephone = request.form.get("numero_telephone", "").strip()
        montant_str      = request.form.get("montant", "").strip()

        # Validation des champs
        if not operateur or not numero_telephone or not montant_str:
            erreur = "Tous les champs sont obligatoires."
        elif operateur not in OPERATEURS:
            erreur = "Opérateur invalide."
        elif not numero_telephone.isdigit() or len(numero_telephone) < 8:
            erreur = "Numéro de téléphone invalide (8 chiffres minimum)."
        else:
            try:
                montant_fcfa = int(montant_str)
            except ValueError:
                erreur = "Montant invalide."
                montant_fcfa = 0

            if not erreur:
                resultat, message_erreur = creer_retrait(
                    utilisateur_id=session["utilisateur_id"],
                    montant_fcfa=montant_fcfa,
                    operateur=operateur,
                    numero_telephone=numero_telephone
                )
                if resultat:
                    # Succès : on recharge l'utilisateur pour avoir le nouveau solde
                    # puis on redirige vers le tableau de bord
                    session["retrait_succes"] = f"Demande de retrait de {montant_fcfa} FCFA envoyée avec succès !"
                    return redirect(url_for("tableau_de_bord"))
                else:
                    erreur = message_erreur

        # Si erreur, on recharge l'utilisateur (son solde n'a pas changé)
        utilisateur = get_utilisateur(session["utilisateur_id"])

    retraits = get_retraits(session["utilisateur_id"])

    return render_template(
        "retrait.html",
        utilisateur=utilisateur,
        operateurs=OPERATEURS,
        retraits=retraits,
        erreur=erreur,
        succes=succes
    )


@app.route("/postback/cpx")
def postback_cpx():
    ext_user_id    = request.args.get("ext_user_id", "")
    amount_usd     = request.args.get("amount_usd", "0")
    transaction_id = request.args.get("transaction_id", "")
    hash_recu      = request.args.get("hash", "")

    hash_attendu = hashlib.md5(
        f"{transaction_id}-{CPX_SECRET}".encode()
    ).hexdigest()

    if hash_recu != hash_attendu:
        return "Invalid hash", 403

    try:
        montant_usd  = float(amount_usd)
        montant_fcfa = int(montant_usd * TAUX_FCFA * PART_UTILISATEUR)
    except ValueError:
        return "Invalid amount", 400

    if montant_fcfa <= 0:
        return "OK", 200

    succes = crediter_solde(
        utilisateur_id=ext_user_id,
        montant_fcfa=montant_fcfa,
        transaction_id=transaction_id,
        source="cpx"
    )

    return ("1", 200) if succes else ("Error", 500)

# ============================================================
# ROUTES ADMIN — À ajouter à la fin de app.py
# (avant le bloc if __name__ == "__main__")
# ============================================================

# Importer les fonctions admin dans le bloc d'import existant :
# from api import (..., admin_get_retraits_en_attente,
#                  admin_valider_retrait, admin_refuser_retrait,
#                  admin_get_stats, admin_get_tous_retraits)

# Mot de passe admin — change cette valeur avant de déployer !
ADMIN_MOT_DE_PASSE = "AdReward@Admin2025"

# URL secrète d'accès à l'admin (ne la partage pas)
# Accessible via : https://ton-app.onrender.com/gestion-ar-admin


@app.route("/gestion-ar-admin", methods=["GET", "POST"])
def admin_connexion():
    # ============================================================
    # Page de connexion admin.
    # Vérifie le mot de passe et ouvre une session admin séparée
    # de la session utilisateur classique.
    # ============================================================
    if session.get("admin_connecte"):
        return redirect(url_for("admin_dashboard"))

    erreur = None
    if request.method == "POST":
        mdp = request.form.get("mot_de_passe", "")
        if mdp == ADMIN_MOT_DE_PASSE:
            session["admin_connecte"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            erreur = "Mot de passe incorrect."

    return render_template("admin_connexion.html", erreur=erreur)


@app.route("/gestion-ar-admin/dashboard")
def admin_dashboard():
    # ============================================================
    # Dashboard principal admin.
    # Affiche les stats et les retraits en attente.
    # ============================================================
    if not session.get("admin_connecte"):
        return redirect(url_for("admin_connexion"))

    stats            = admin_get_stats()
    retraits_attente = admin_get_retraits_en_attente()
    tous_retraits    = admin_get_tous_retraits()

    return render_template(
        "admin.html",
        stats=stats,
        retraits_attente=retraits_attente,
        tous_retraits=tous_retraits
    )


@app.route("/gestion-ar-admin/valider/<retrait_id>", methods=["POST"])
def admin_valider(retrait_id):
    # ============================================================
    # Valide un retrait (passe son statut à "validé").
    # L'argent a déjà été déduit du solde lors de la demande,
    # donc on ne touche pas au solde ici.
    # ============================================================
    if not session.get("admin_connecte"):
        return redirect(url_for("admin_connexion"))

    admin_valider_retrait(retrait_id)
    return redirect(url_for("admin_dashboard"))


@app.route("/gestion-ar-admin/refuser/<retrait_id>", methods=["POST"])
def admin_refuser(retrait_id):
    # ============================================================
    # Refuse un retrait ET rembourse l'utilisateur.
    # ============================================================
    if not session.get("admin_connecte"):
        return redirect(url_for("admin_connexion"))

    admin_refuser_retrait(retrait_id)
    return redirect(url_for("admin_dashboard"))


@app.route("/gestion-ar-admin/deconnexion")
def admin_deconnexion():
    session.pop("admin_connecte", None)
    return redirect(url_for("admin_connexion"))

if __name__ == "__main__":
    app.run(debug=True)