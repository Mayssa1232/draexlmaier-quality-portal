import streamlit as strl
import pandas as pd
import sys
import os
import plotly.express as px
import streamlit_authenticator as stauth
import psycopg2
from psycopg2.extras import RealDictCursor

st = strl  # Pour la compatibilité avec votre reste de code utilisant 'strl'

# 1. Configurer la page (TOUJOURS EN PREMIER)
st.set_page_config(page_title="DRÄXLMAIER Quality Portal", layout="wide")

# --- PATH & IMPORT ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from run_pipeline import extract_dynamic_pdf_data, get_db_connection

# --- CHARGEMENT DYNAMIQUE DES UTILISATEURS DEPUIS NEON ---
def load_users_from_db():
    credentials = {"usernames": {}}
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT username, name, password_hash, email FROM users;")
        rows = cur.fetchall()
        for row in rows:
            credentials["usernames"][row["username"]] = {
                "name": row["name"],
                "password": row["password_hash"], # stauth compare directement avec le hash
                "email": row["email"]
            }
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Erreur de connexion à la base de données des utilisateurs : {e}")
    return credentials

# Charger les comptes existants
credentials = load_users_from_db()

authenticator = stauth.Authenticate(
    credentials,
    'quality_portal_cookie',
    'signature_key_12345',
    cookie_expiry_days=30
)

# --- INTERFACE DE BIENVENUE (CONNEXION / INSCRIPTION) ---
if not st.session_state.get("authentication_status"):
    # Afficher deux onglets au centre de l'écran si l'utilisateur n'est pas connecté
    auth_tab1, auth_tab2 = st.tabs(["🔑 Se connecter", "📝 S'inscrire / Créer un compte"])
    
    with auth_tab1:
        authenticator.login()
        if st.session_state.get("authentication_status") == False:
            st.error("Identifiant ou mot de passe incorrect.")
        elif st.session_state.get("authentication_status") == None:
            st.info("Veuillez vous connecter pour accéder à l'application.")
            
    with auth_tab2:
        st.subheader("Créer un nouveau compte d'auditeur")
        with st.form("registration_form", clear_on_submit=True):
            new_username = st.text_input("Identifiant (ex: mayssa)").strip().lower()
            new_name = st.text_input("Nom Complet (ex: Mayssa Quality)")
            new_email = st.text_input("Adresse E-mail Professionnelle (ex: mayssa@draxlmaier.com)").strip()
            new_password = st.text_input("Mot de passe", type="password")
            confirm_password = st.text_input("Confirmer le mot de passe", type="password")
            
            submit_reg = st.form_submit_button("S'inscrire")
            
            if submit_reg:
                if not new_username or not new_name or not new_email or not new_password:
                    st.error("Tous les champs sont obligatoires.")
                elif new_password != confirm_password:
                    st.error("Les mots de passe ne correspondent pas.")
                elif "@" not in new_email:
                    st.error("Veuillez entrer une adresse e-mail valide.")
                else:
                    # Hachage sécurisé du mot de passe via streamlit_authenticator
                    hashed_password = stauth.Hasher.hash(new_password)
                    
                    try:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        # Vérifier si l'identifiant ou l'email existe déjà
                        cur.execute("SELECT username FROM users WHERE username = %s OR email = %s", (new_username, new_email))
                        if cur.fetchone():
                            st.error("Cet identifiant ou cet e-mail est déjà utilisé.")
                        else:
                            # Insertion du nouvel utilisateur
                            cur.execute(
                                "INSERT INTO users (username, name, password_hash, email) VALUES (%s, %s, %s, %s)",
                                (new_username, new_name, hashed_password, new_email)
                            )
                            conn.commit()
                            st.success("Compte créé avec succès ! Vous pouvez maintenant vous connecter dans l'onglet associé.")
                            # Forcer le rechargement pour que le nouveau compte soit immédiatement reconnu
                            st.rerun()
                        cur.close()
                        conn.close()
                    except Exception as e:
                        st.error(f"Erreur lors de l'enregistrement : {e}")

# --- ZONE SÉCURISÉE (L'UTILISATEUR EST CONNECTÉ) ---
if st.session_state.get("authentication_status"):
    name = st.session_state["name"]
    username = st.session_state["username"]
    
    # Déconnexion dans la barre latérale
    authenticator.logout('Déconnexion', 'sidebar')
    st.sidebar.title(f"Bienvenue {name}")
    
    # Récupérer l'email de l'utilisateur connecté depuis le dictionnaire chargé
    user_email_session = credentials['usernames'][username]['email']
    st.session_state['user_email'] = user_email_session

    # =========================================================================
    # TOUT LE RESTE DE VOTRE CODE (DESIGN, ONGLETS DE TRAVAIL, INJECTION) RESTE ICI
    # (Veillez à ce que tout soit indenté d'un bloc de 4 espaces !)
    # =========================================================================

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