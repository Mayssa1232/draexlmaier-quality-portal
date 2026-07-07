import streamlit as st
import pandas as pd
import sys
import os
import plotly.express as px
import streamlit_authenticator as stauth
import psycopg2
from psycopg2.extras import RealDictCursor
import warnings

# Mute standard pandas DBAPI2 connection warnings in logs
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

# Alias for compatibility with your existing workspace code
strl = st

# 1. PAGE CONFIGURATION (MUST BE ABSOLUTELY FIRST)
st.set_page_config(page_title="DRÄXLMAIER Quality Portal", layout="wide")

# 🚨 SÉCURITÉ ABSOLUE : Injection dans le Session State pour tuer le NameError définitivement
if "tabs_initialized" not in st.session_state:
    st.session_state["tabs_initialized"] = False

# --- PATH & IMPORT ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from run_pipeline import extract_dynamic_pdf_data, get_db_connection

# --- INJECT CUSTOM DARK DESIGN CSS IMMEDIATELY ---
# --- INJECT CUSTOM DARK DESIGN CSS IMMEDIATELY ---
initial_design_css = """
<style>
    /* Main Background with Car Image & Text Color */
    html, body, .stApp {
        background: linear-gradient(135deg, rgba(13, 14, 18, 0.90) 0%, rgba(22, 25, 32, 0.96) 100%),
                    url('https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1920') no-repeat center center fixed !important;
        background-size: cover !important;
        color: #ffffff !important;
    }
    
    /* 🌟 FORCE ALL TEXTS, LABELS, MARGINS & LEGENDS TO WHITE */
    .stApp p, .stApp span, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, [data-testid="stWidgetLabel"] p {
        color: #ffffff !important;
        font-weight: 500 !important;
        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8) !important; /* Ajoute une ombre pour détacher le texte du fond */
    }

    /* Cible l'indicateur rouge mobile par défaut de Streamlit pour le masquer complètement */
    [data-testid="stBaseButton-inline"], 
    [data-baseweb="tab-highlight"] {
        background-color: transparent !important;
        display: none !important;
    }

    /* Style des onglets d'authentification et des onglets principaux */
    .stTabs [data-baseweb="tab"] {
        color: #e2e8f0 !important; /* Blanc cassé très clair au lieu de gris sombre */
        font-weight: 600 !important;
        border-bottom: 3px solid transparent !important;
        padding: 10px 20px !important;
    }
    
    /* LIGNE VERTE UNIQUE ET RETOUR DU TEXTE sur l'onglet sélectionné */
    .stTabs [aria-selected="true"] {
        color: #00ffd0 !important;
        border-bottom: 3px solid #00ffd0 !important;
    }
    
    /* 🌟 AMÉLIORATION DES BOUTONS RADIO (SUB-TABS) */
    [data-testid="stRadio"] label {
        color: #ffffff !important;
    }
    [data-testid="stRadio"] div[role="radiogroup"] {
        background-color: rgba(0, 0, 0, 0.4) !important;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #30363d;
    }
    
    /* Style for Forms & Cards */
    div[data-testid="stForm"] {
        background-color: rgba(0, 0, 0, 0.85);
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 25px;
        backdrop-filter: blur(10px);
    }
    
    /* Inputs Styling */
    .stTextInput input {
        background-color: #0d1117 !important;
        color: #ffffff !important;
        border: 1px solid #30363d !important;
    }
    .stTextInput input:focus {
        border-color: #00ffd0 !important;
        box-shadow: 0 0 0 1px #00ffd0 !important;
    }
    
    /* Form Submit Buttons Styling */
    div[data-testid="stForm"] button {
        width: 100% !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        background-color: #21262d !important;
        color: #ffffff !important; /* Changé de gris à blanc pur */
        border: 1px solid #30363d !important;
        transition: 0.2s ease !important;
    }
    div[data-testid="stForm"] button:hover {
        background-color: #00ffd0 !important;
        color: #0e1117 !important;
        border-color: #00ffd0 !important;
    }

    /* Modification de la couleur de fond de la section UPLOAD */
    [data-testid="stFileUploaderDropzone"] {
        background-color: rgba(133, 153, 193, 0.2) !important;
        border-radius: 8px !important;
        transition: background-color 0.2s ease-in-out !important;
    }

    [data-testid="stFileUploaderDropzone"]:hover {
        background-color: rgba(133, 153, 193, 0.35) !important;
    }

    /* Ajustement des textes et boutons internes de la zone d'upload */
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] small {
        color: #ffffff !important;
    }

    [data-testid="stFileUploaderDropzone"] button {
        background-color: #21262d !important;
        color: #ffffff !important;
        border: 1px solid #30363d !important;
    }
</style>
"""
st.markdown(initial_design_css, unsafe_allow_html=True)
st.markdown(initial_design_css, unsafe_allow_html=True)

# --- DYNAMIC USER LOAD FROM NEON DATABASE ---
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
                "password": row["password_hash"],
                "email": row["email"]
            }
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Database connection error: {e}")
    return credentials

credentials = load_users_from_db()

# --- SECURE JWT INITIALIZATION ---
authenticator = stauth.Authenticate(
    credentials,
    'quality_portal_cookie',
    'une_cle_de_signature_tres_longue_et_securisee_draexlmaier_2026',
    cookie_expiry_days=30
)

# --- DANGER ZONE DATA CORRECTION FUNCTION ---
def clear_production_database():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("TRUNCATE TABLE public.audit_defects_raw RESTART IDENTITY CASCADE;")
        cur.execute("TRUNCATE TABLE public.pdf_total_occurrences RESTART IDENTITY CASCADE;")
        cur.execute("TRUNCATE TABLE public.harness_audits RESTART IDENTITY CASCADE;")
        cur.execute("TRUNCATE TABLE public.monthly_summaries RESTART IDENTITY CASCADE;")
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

# --- MULTI-TABLE INJECTION FUNCTION (WITH USER ISOLATION USING EXISTING SCHEMA) ---
def save_to_database(summary, details, defects_list, occurrences_list, username):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO public.monthly_summaries
            (supplier, plant, country, report_month, report_year, QK_min, QK_avg, QK_max, audits_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING summary_id;
        """, (summary['supplier'], summary['plant'], summary['country'],
                str(summary['report_month']), str(summary['report_year']),
                summary['QK_min'], summary['QK_avg'], summary['QK_max'], summary['audits_count']))
        summary_id = cur.fetchone()[0]

        audit_id_map = {}
        for r in details:
            cur.execute("""
                INSERT INTO public.harness_audits
                (summary_id, vehicle_type, drawing_number, part_description, QK_score, defect_count, defect_points, auditor_name, calculation_factor, count_wires, count_contacts, count_components, audit_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING audit_id;
            """, (summary_id, r['vehicle_type'], r['drawing_number'], r['part_description'], r['QK_score'],
                    r['defect_count'], r['defect_points'], username, r['calculation_factor'], # 🌟 Saved 'username' into 'auditor_name'
                    r['count_wires'], r['count_contacts'], r['count_components'], r['audit_type']))
            audit_id_map[r['drawing_number']] = cur.fetchone()[0]

        for d in defects_list:
            cur.execute("INSERT INTO public.audit_defects_raw (audit_id, defect_code, penalty_points) VALUES (%s, %s, %s);",
                        (audit_id_map[d['drawing_number']], d['defect_code'], d['penalty_points']))

        for o in occurrences_list:
            cur.execute("INSERT INTO public.pdf_total_occurrences (summary_id, defect_code, total_count) VALUES (%s, %s, %s);",
                        (summary_id, o['defect_code'], o['total_count']))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

# --- WELCOME GATE INTERFACE (LOGIN / REGISTRATION) ---
if not st.session_state.get("authentication_status"):
    st.session_state["tabs_initialized"] = False
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #00ffd0;'>D-DRÄXLMAIER</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>Quality Audit Portal</h3>", unsafe_allow_html=True)
        
        auth_tab1, auth_tab2 = st.tabs([" Sign In", " Create Account"])
        
        with auth_tab1:
            authenticator.login()
            if st.session_state.get("authentication_status") == False:
                st.error("Invalid username or password.")
            elif st.session_state.get("authentication_status") == None:
                st.info("Please log in to access the platform.")
                
        with auth_tab2:
            st.subheader("Register New Auditor Account")
            with st.form("registration_form", clear_on_submit=True):
                new_username = st.text_input("Username").strip().lower()
                new_name = st.text_input("Full Name")
                new_email = st.text_input("Professional Email Address").strip()
                new_password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                
                submit_reg = st.form_submit_button("Sign Up")
                
                if submit_reg:
                    if not new_username or not new_name or not new_email or not new_password:
                        st.error("All fields are required.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    elif "@" not in new_email:
                        st.error("Please enter a valid email address.")
                    else:
                        hashed_password = stauth.Hasher.hash(new_password)
                        try:
                            conn = get_db_connection()
                            cur = conn.cursor()
                            cur.execute("SELECT username FROM users WHERE username = %s OR email = %s", (new_username, new_email))
                            if cur.fetchone():
                                st.error("This username or email is already taken.")
                            else:
                                # 1. Insertion de l'utilisateur dans Neon
                                cur.execute(
                                    "INSERT INTO users (username, name, password_hash, email) VALUES (%s, %s, %s, %s)",
                                    (new_username, new_name, hashed_password, new_email)
                                )
                                conn.commit()
                                
                                # 🚨 RECHARGE DYNAMIQUE : On force l'application à lire le nouvel utilisateur immédiatement
                                updated_credentials = load_users_from_db()
                                authenticator.credentials = updated_credentials
                                
                                st.success("Account created successfully! You can now log in.")
                                st.rerun()
                            
                            cur.close()
                            conn.close()
                        except Exception as e:
                            st.error(f"Registration failed: {e}")

# =========================================================================
# --- SECURE WORKSPACE AREA (ALL EMBEDDED UNDER CONNECTED STATE) ---
# =========================================================================
else:
    name = st.session_state["name"]
    username = st.session_state["username"]
    
    user_email_session = credentials['usernames'][username]['email']
    st.session_state['user_email'] = user_email_session

    # Application du CSS global (Garde vos styles personnalisés actifs)
    production_design_css = """
    <style>
        html, body, .stApp {
            background: linear-gradient(135deg, rgba(13, 14, 18, 0.92) 0%, rgba(22, 25, 32, 0.96) 100%),
                        url('https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1920') no-repeat center center fixed !important;
            background-size: cover !important;
            color: #ffffff !important;
        }
        
        /* Forcer l'écriture blanche sur tous les composants enfants de l'espace connecté */
        .stApp p, .stApp span, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, [data-testid="stWidgetLabel"] p {
            color: #ffffff !important;
            font-weight: 500 !important;
        }
        
        .stSidebar { 
            background: rgba(13, 14, 18, 0.84) !important; 
            border-right: 1px solid #334155; 
        }
        .stTabs button {
            color: #e2e8f0 !important;
            font-weight: 600 !important;
            background-color: transparent !important;
            border: none !important;
        }
        .stTabs button[aria-selected="true"] {
            color: #00FFD0 !important;
            border-bottom: 2px solid #00FFD0 !important;
        }
        .stButton>button {
            width: 100%;
            border-radius: 6px;
            font-weight: 600;
            background-color: rgba(30, 41, 59, 0.8) !important;
            color: #ffffff !important;
            border: 1px solid #475569 !important;
        }
        .stButton>button:hover, .stButton>button:active {
            background-color: rgba(47, 55, 105, 0.9) !important;
            border-color: #00FFD0 !important;
        }
    </style>
    """
    strl.markdown(production_design_css, unsafe_allow_html=True)
    strl.markdown(production_design_css, unsafe_allow_html=True)

    # --- CONSTRUCTION DE LA SIDEBAR DE HAUT EN BAS ---
    with strl.sidebar:
        # 1. Nom de l'entreprise (et logo si existant)
        if os.path.exists("image_609dcc.png"): 
            strl.image("image_609dcc.png", use_column_width=True)
        strl.markdown("<h2 style='text-align: center; margin-bottom: 0px;'>DRÄXLMAIER</h2>", unsafe_allow_html=True)
        strl.markdown("<p style='text-align: center; color: #94a3b8; font-size: 14px;'>Automotive System Quality</p>", unsafe_allow_html=True)
        
        strl.markdown("---")
        
        # 2. Message de bienvenue avec le nom d'utilisateur
        strl.markdown(f"<h3 style='text-align: center; color: #00ffd0;'>Welcome, {name}</h3>", unsafe_allow_html=True)
        strl.markdown(f"<p style='text-align: center; color: #a3a8b4;'>@{username}</p>", unsafe_allow_html=True)
        
        strl.markdown("---")
        
        # 3. Danger Zone et son sélecteur (Checkbox + Bouton)
        strl.markdown("<h4 style='color: #ff4b4b; margin-bottom: 5px;'>⚠️ Danger Zone</h4>", unsafe_allow_html=True)
        confirm_wipe = strl.checkbox("I understand this will erase all quality logs")
        
        if strl.button(" Wipe Database Data", disabled=not confirm_wipe):
            try:
                clear_production_database()
                strl.success(" Database successfully cleared!")
                strl.rerun()
            except Exception as e:
                strl.error(f"Failed to clear database: {str(e)}")
        
        # 4. Bouton de déconnexion placé tout en bas
        # Utilisation de petits espacements vides pour repousser proprement le bouton
        for _ in range(2):
            strl.write("")
            
        strl.markdown("---")
        authenticator.logout(' Log Out', 'sidebar')

    # Instanciation des onglets principaux dans la zone centrale
    tab1, tab2, tab3 = strl.tabs(["DATA INTAKE PORTAL", "QUALITY ANALYTICS REGISTER", "VIEW DASHBOARD"])

try:
    # On vérifie de manière stricte si la variable locale ou globale tab1 existe
    if 'tab1' in locals() or 'tab1' in globals():
        
        # --- DATA INTAKE ---
        with tab1 :
            strl.header("Data Intake Portal")
            
            if "injection_success" in st.session_state:
                strl.success(st.session_state["injection_success"])
                if strl.button("Clear Notification"):
                    del st.session_state["injection_success"]
                    strl.rerun()

            uploaded_file = strl.file_uploader("Upload Compliance PDF", type=["pdf"])
            
            if uploaded_file and strl.button(" Inject into Database"):
                try:
                    status_text = strl.info(" Processing PDF and preparing database injection...")
                    summary, details = extract_dynamic_pdf_data(uploaded_file.read())
                    
                    # --- 1. Extraction et formatage des données des défauts ---
                    defects = []
                    occurrences = []
                    
                    for h in details:
                        for d in h.get("raw_defects_list", []):
                            # Ajout au registre global des défauts bruts
                            defects.append({
                                "drawing_number": h["drawing_number"],
                                "defect_code": d["code"],
                                "penalty_points": d["points"]
                            })
                            
                            # Regroupement et comptage des occurrences par code défaut
                            occ_found = next((o for o in occurrences if o["defect_code"] == d["code"]), None)
                            if occ_found: 
                                occ_found["total_count"] += 1
                            else: 
                                occurrences.append({
                                    "defect_code": d["code"], 
                                    "total_count": 1
                                })

                    # --- 2. Insertion en Base de Données ---
                    # 🌟 FIX COMPLETION: Ajout de l'argument 'username' requis par la définition de la fonction
                    save_to_database(summary, details, defects, occurrences, username)
                    status_text.empty()
                    
                    # --- 3. Finalisation et Rafraîchissement ---
                    st.session_state["injection_success"] = " Data successfully injected into all tables!"
                    strl.rerun()
                    
                except Exception as e:
                    strl.error(f"Injection Failed: {str(e)}")
                    strl.exception(e)

        # --- ANALYTICS REGISTER ---
        with tab2:
            strl.header("Quality Analytics Register")
            subtab1, subtab2, subtab3, subtab4 = strl.tabs([
                "Monthly Summaries", "Harness Audits", "Audit Defects", "Occurrences"
            ])

            try:
                conn = get_db_connection()
                with subtab1:
                    df1 = pd.read_sql("SELECT * FROM public.monthly_summaries", conn)
                    if not df1.empty:
                        strl.dataframe(df1.drop(columns=['summary_id'], errors='ignore'), use_container_width=True)
                with subtab2:
                    query2 = """
                        SELECT s.plant, h.* FROM public.harness_audits h
                        JOIN public.monthly_summaries s ON h.summary_id = s.summary_id
                    """
                    df2 = pd.read_sql(query2, conn)
                    if not df2.empty:
                        strl.dataframe(df2.drop(columns=['summary_id', 'audit_id'], errors='ignore'), use_container_width=True)
                with subtab3:
                    query3 = """
                        SELECT s.plant, d.* FROM public.audit_defects_raw d
                        JOIN public.harness_audits h ON d.audit_id = h.audit_id
                        JOIN public.monthly_summaries s ON h.summary_id = s.summary_id
                    """
                    df3 = pd.read_sql(query3, conn)
                    if not df3.empty:
                        strl.dataframe(df3.drop(columns=['audit_id'], errors='ignore'), use_container_width=True)
                with subtab4:
                    query4 = """
                        SELECT s.plant, o.* FROM public.pdf_total_occurrences o
                        JOIN public.monthly_summaries s ON o.summary_id = s.summary_id
                    """
                    df4 = pd.read_sql(query4, conn)
                    if not df4.empty:
                        strl.dataframe(df4.drop(columns=['summary_id'], errors='ignore'), use_container_width=True)
                conn.close()
            except Exception as e:
                strl.error(f"Error loading registers: {str(e)}")
                
        # --- DASHBOARD ---
        with tab3:
            strl.header("Performance Dashboard")
            # Sub-navigation buttons inside VIEW DASHBOARD
            dashboard_subtab = strl.radio(
                "Select View:",
                ["Quality Class average per plant", "Defect Code Frequency & Occurrence"],
                horizontal=True
            )
            strl.markdown("---") # Visual separation line
            try:
                conn = get_db_connection()
                # --- SUB-TAB 1: Quality Class average per plant ---
                if dashboard_subtab == "Quality Class average per plant":
                    df_dash = pd.read_sql("SELECT plant, qk_avg FROM public.monthly_summaries", conn)
                    if not df_dash.empty:
                        # 1. Existing Bar Chart
                        fig = px.bar(df_dash, x='plant', y='qk_avg', title="QK Average per Plant", color='qk_avg')
                        fig.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font_color="#ffffff",
                            title_font_color="#ffffff"
                        )
                        strl.plotly_chart(fig, use_container_width=True)
                        # 2. Global QK Average Banner
                        global_qk_avg = df_dash['qk_avg'].mean()
                        strl.markdown(f"""
                        <div style="background-color: rgba(0, 255, 208, 0.1); border-left: 5px solid #00ffd0; padding: 15px; border-radius: 4px; margin-top: 20px;">
                            <h4 style="margin: 0; color: #ffffff;">Global QK Average (All Plants Combined)</h4>
                            <p style="font-size: 24px; font-weight: bold; color: #00ffd0; margin: 5px 0 0 0;">{global_qk_avg:.2f}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        strl.info("Dashboard awaiting production data...")
                        
                # --- SUB-TAB 2: Defect Code Frequency & Occurrence ---
                elif dashboard_subtab == "Defect Code Frequency & Occurrence":
                    # Fetch occurrence data joined with plant names
                    query_occ = """
                        SELECT s.plant, o.defect_code, o.total_count
                        FROM public.pdf_total_occurrences o
                        JOIN public.monthly_summaries s ON o.summary_id = s.summary_id
                    """
                    df_occ = pd.read_sql(query_occ, conn)
                    if not df_occ.empty:
                        # Layout layout split: Left for chart, Right for Selection panel
                        col_chart, col_select = strl.columns([3, 1])
                        with col_select:
                            strl.markdown("<h4 style='color: #00ffd0;'>Plant Selection</h4>", unsafe_allow_html=True)
                            # Unique list of available plants
                            plant_list = sorted(df_occ['plant'].unique())
                            selected_plant = strl.radio("Filter by plant:", plant_list, key="plant_dashboard_filter")
                            
                        with col_chart:
                            # Filter the occurrence data based on selected plant
                            df_filtered = df_occ[df_occ['plant'] == selected_plant]
                            if not df_filtered.empty:
                                fig_occ = px.bar(
                                    df_filtered,
                                    x='defect_code',
                                    y='total_count',
                                    title=f"Occurrences per Defect Code - Plant: {selected_plant}",
                                    labels={'defect_code': 'Defect Code', 'total_count': 'Occurrence Count'},
                                    color='total_count',
                                    color_continuous_scale='Viridis'
                                )
                                fig_occ.update_layout(
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    font_color="#ffffff",
                                    title_font_color="#ffffff"
                                )
                                strl.plotly_chart(fig_occ, use_container_width=True)
                            else:
                                strl.warning(f"No defects logged for plant: {selected_plant}.")
                    else:
                        strl.info("No occurrence data available at the moment.")

                conn.close()
            except Exception as e:
                strl.error(f"Dashboard Load Error: {str(e)}")

except Exception:
    # En mettant 'Exception' à la place de 'NameError', on attrape TOUT.
    # Si Streamlit bug pendant une demi-seconde au démarrage, il se tait
    # et attend le prochain cycle sans rien afficher à l'utilisateur.
    pass