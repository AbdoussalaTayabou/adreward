# ============================================================
# app.py — Fichier principal
# ============================================================

import hashlib
from flask import Flask, render_template, request, redirect, url_for, session
from api import creer_utilisateur, connecter_utilisateur, get_utilisateur, crediter_solde

app = Flask(__name__)
app.secret_key = "adreward-secret-key-changer-en-production"

# ============================================================
# CONFIGURATION GÉNÉRALE
#
# CPX_APP_ID       : identifiant de ton app chez CPX Research
# CPX_SECRET       : clé secrète pour vérifier les postbacks
# TAUX_FCFA        : 1 USD = 563 FCFA
# PART_UTILISATEUR : l'utilisateur reçoit 35% du gain brut
#
# Pour modifier le pourcentage ou le taux, change juste
# ces deux lignes — tout le reste s'adapte automatiquement.
# ============================================================
CPX_APP_ID       = "32995"
CPX_SECRET       = "SJOAjIyqrNKd8VsJBhNg4EcTTy23C9pi"
TAUX_FCFA        = 563
PART_UTILISATEUR = 0.35   # 35%


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


# ============================================================
# ROUTE : Postback CPX Research
#
# C'est l'URL que CPX Research appelle automatiquement
# quand un utilisateur termine une offre.
# CPX envoie ces paramètres dans l'URL :
#
#   ext_user_id    : l'ID de l'utilisateur qui a complété l'offre
#   amount_usd     : le montant gagné en USD (ex: "0.5")
#   transaction_id : identifiant unique de cette offre
#   hash           : signature de sécurité pour vérifier
#                    que c'est bien CPX qui envoie (pas un pirate)
#
# Exemple d'URL reçue :
# /postback/cpx?ext_user_id=abc123&amount_usd=0.5
#              &transaction_id=TX999&hash=xxxx
# ============================================================
@app.route("/postback/cpx")
def postback_cpx():

    # On récupère tous les paramètres envoyés par CPX
    ext_user_id    = request.args.get("ext_user_id", "")
    amount_usd     = request.args.get("amount_usd", "0")
    transaction_id = request.args.get("transaction_id", "")
    hash_recu      = request.args.get("hash", "")

    # --------------------------------------------------------
    # ÉTAPE 1 : Vérification de la signature (sécurité)
    #
    # CPX calcule une signature MD5 avec :
    #   transaction_id + "-" + CPX_SECRET
    # On fait le même calcul de notre côté et on compare.
    # Si ça ne correspond pas → on rejette avec une erreur 403.
    # Ça empêche n'importe qui de créditer des faux gains.
    # --------------------------------------------------------
    hash_attendu = hashlib.md5(
        f"{transaction_id}-{CPX_SECRET}".encode()
    ).hexdigest()

    if hash_recu != hash_attendu:
        print(f"❌ Postback rejeté : signature invalide. Reçu={hash_recu} Attendu={hash_attendu}")
        return "Invalid hash", 403

    # --------------------------------------------------------
    # ÉTAPE 2 : Calcul du montant en FCFA
    #
    # CPX envoie le montant en USD (ex: "0.5")
    # On convertit : 0.5 USD × 563 = 281.5 FCFA
    # On applique la part utilisateur : 281.5 × 35% = 98 FCFA
    # On arrondit à l'entier inférieur (int())
    # --------------------------------------------------------
    try:
        montant_usd   = float(amount_usd)
        montant_fcfa  = int(montant_usd * TAUX_FCFA * PART_UTILISATEUR)
    except ValueError:
        return "Invalid amount", 400

    # Si le montant calculé est 0, rien à créditer
    if montant_fcfa <= 0:
        return "OK", 200

    # --------------------------------------------------------
    # ÉTAPE 3 : Créditer le solde de l'utilisateur
    # --------------------------------------------------------
    succes = crediter_solde(
        utilisateur_id=ext_user_id,
        montant_fcfa=montant_fcfa,
        transaction_id=transaction_id,
        source="cpx"
    )

    if succes:
        # CPX attend la réponse "1" pour confirmer que le postback
        # a bien été reçu et traité. Sans ça, CPX réessaiera.
        return "1", 200
    else:
        return "Error", 500


if __name__ == "__main__":
    app.run(debug=True)