import streamlit as strl
import pandas as pd
import sys
import os
import plotly.express as px
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# 1. Configurer la page (TOUJOURS EN PREMIER)
strl.set_page_config(page_title="DRÄXLMAIER Quality Portal", layout="wide")

# --- PATH & IMPORT ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from run_pipeline import extract_dynamic_pdf_data, get_db_connection

# 2. Configuration des comptes
credentials = {
    "usernames": {
        "mayssa": {
            "name": "Mayssa Quality",
            "password": "mot_de_passe_hache_ou_clair_1", 
            "email": "mayssa@draxlmaier.com"
        },
        "ahmed": {
            "name": "Ahmed Quality",
            "password": "mot_de_passe_hache_ou_clair_2",
            "email": "ahmed@draxlmaier.com"
        }
    }
}

authenticator = stauth.Authenticate(
    credentials,
    'quality_portal_cookie',
    'signature_key_12345',
    cookie_expiry_days=30
)

# 3. Affichage du formulaire de connexion
# 3. Affichage du formulaire de connexion (Nouvelle syntaxe sans dépaquetage)
authenticator.login()

# Vérification du statut via st.session_state (géré automatiquement par le module)
if strl.session_state.get("authentication_status") == False:
    strl.error("Identifiant ou mot de passe incorrect.")

elif strl.session_state.get("authentication_status") == None:
    strl.warning("Veuillez entrer votre identifiant et votre mot de passe pour accéder au portail.")

elif strl.session_state.get("authentication_status"):
    # L'UTILISATEUR EST CONNECTÉ AVEC SUCCÈS
    
    # Récupérer les informations de l'utilisateur connecté depuis la session
    name = strl.session_state["name"]
    username = strl.session_state["username"]
    
    # Bouton de déconnexion dans la barre latérale
    authenticator.logout('Déconnexion', 'sidebar')
    strl.sidebar.title(f"Bienvenue {name}")
    
    # Sauvegarder l'email de l'utilisateur connecté en mémoire de session pour vos filtres SQL
    user_email_session = credentials['usernames'][username]['email']
    strl.session_state['user_email'] = user_email_session

    # =========================================================================
    # TOUT LE RESTE DE VOTRE CODE (DESIGN, ONGLETS, INJECTION) RESTE ICI
    # (Pensez à garder l'indentation de 4 espaces pour tout ce bloc !)
    # =========================================================================

    # --- CSS & DESIGN ---
    design_css = """
    <style>
        /* Votre CSS existant... */
    </style>
    """
    strl.markdown(design_css, unsafe_allow_html=True)

    # --- FONCTION D'INJECTION MULTI-TABLES ---
    def save_to_database(summary, details, defects_list, occurrences_list):
        # Votre code d'injection existant...
        pass

    # --- SIDEBAR COMPOSANTS ---
    with strl.sidebar:
        if os.path.exists("logo.png"): strl.image("logo.png", use_column_width=True)
        strl.markdown("<h2 style='text-align: center;'>D-DRÄXLMAIER</h2>", unsafe_allow_html=True)

    # --- TABS ---
    tab1, tab2, tab3 = strl.tabs(["DATA INTAKE PORTAL", "QUALITY ANALYTICS REGISTER", "VIEW DASHBOARD"])

    # --- DATA INTAKE ---
    with tab1:
        # Votre code d'extraction et d'injection existant...
        pass

    # --- ANALYTICS REGISTER FILTRÉ ---
    with tab2:
        # Votre code d'affichage des grilles SQL filtrées existant...
        pass

    # --- DASHBOARD FILTRÉ ---
    with tab3:
        # Votre code d'affichage des graphiques Plotly existant...
        pass