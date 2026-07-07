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

# SÉCURITÉ ABSOLUE : Injection dans le Session State pour tuer le NameError définitivement
if "tabs_initialized" not in st.session_state:
    st.session_state["tabs_initialized"] = False

# --- PATH & IMPORT ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from run_pipeline import extract_dynamic_pdf_data, get_db_connection

# --- UN_BLOC_CSS_UNIQUE_POUR_TOUTE_L_APPLICATION ---
# --- UN_BLOC_CSS_UNIQUE_POUR_TOUTE_L_APPLICATION ---
global_design_css = """
<style>
    /* Main Background with Car Image & Text Color */
    html, body, .stApp {
        background: linear-gradient(135deg, rgba(13, 14, 18, 0.90) 0%, rgba(22, 25, 32, 0.96) 100%),
                    url('https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1920') no-repeat center center fixed !important;
        background-size: cover !important;
        color: #ffffff !important;
    }
    
    /* FORCE ALL TEXTS, LABELS, MARGINS & LEGENDS TO WHITE */
    .stApp p, .stApp span, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, [data-testid="stWidgetLabel"] p {
        color: #ffffff !important;
        font-weight: 500 !important;
        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8) !important;
    }

    /* CONSERVATION DE LA LIGNE ROUGE NATIVE */
    .stTabs [data-baseweb="tab-highlight"],
    [data-testid="stActiveTabIndicator"] {
        background-color: #ff4b4b !important;
        display: block !important;
        height: 3px !important;
    }

    /* Style des onglets principaux (Pas de ligne verte) */
    .stTabs [data-baseweb="tab"], .stTabs [role="tab"] {
        color: #e2e8f0 !important;
        font-weight: 600 !important;
        border-bottom: none !important;
        padding: 10px 20px !important;
        background-color: transparent !important;
        box-shadow: none !important;
    }
    
    /* Onglet sélectionné */
    .stTabs [aria-selected="true"] {
        color: #ff4b4b !important;
        border-bottom: none !important;
        background-color: transparent !important;
    }
    
    /* MODIFICATION DU BLOC : NOIR TRANSPARENT ET FLOU DE FOND */
    div[data-testid="stForm"], [data-testid="stForm"] {
        background-color: rgba(0, 0, 0, 0.65) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        padding: 30px !important;
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
    }
    
    /* Inputs Styling */
    .stTextInput input {
        background-color: rgba(13, 17, 23, 0.8) !important;
        color: #ffffff !important;
        border: 1px solid #30363d !important;
    }
    .stTextInput input:focus {
        border-color: #ff4b4b !important;
        box-shadow: 0 0 0 1px #ff4b4b !important;
    }
    
    /* MODIFICATION DES BOUTONS : FONCÉS POUR S'ACCORDER AVEC LE TEXTE BLANC */
    .stButton>button,
    div[data-testid="stForm"] button[data-testid="baseButton-secondary"] {
        width: 100% !important;
        height: 45px !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        background-color: #12161a !important; /* Couleur très foncée */
        color: #ffffff !important;            /* Écriture blanc pur très lisible */
        border: 1px solid #ff4b4b !important; /* Fine bordure rouge élégante */
        transition: 0.2s ease !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3) !important;
    }
    .stButton>button:hover,
    div[data-testid="stForm"] button[data-testid="baseButton-secondary"]:hover {
        background-color: #ff4b4b !important;
        color: #ffffff !important;
        border-color: #ff4b4b !important;
        cursor: pointer;
    }

    /* NEUTRALISATION DU BOUTON DE L'ŒIL DU MOT DE PASSE */
    .stTextInput button,
    .stTextInput div[data-testid="InputWithAdornment"] button,
    .stTextInput button[property="password-visibility"] {
        width: 32px !important;
        max-width: 32px !important;
        min-width: 32px !important;
        height: 32px !important;
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
        position: absolute !important;
        right: 8px !important;
        top: 4px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    .stTextInput button:hover {
        background: transparent !important;
        color: #ff4b4b !important;
    }

    /* Style de la Sidebar */
    .stSidebar { 
        background: rgba(13, 14, 18, 0.84) !important; 
        border-right: 1px solid #334155; 
    }
</style>
"""
# Une seule injection propre au démarrage
st.markdown(global_design_css, unsafe_allow_html=True)

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

# --- MULTI-TABLE INJECTION FUNCTION ---
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
                    r['defect_count'], r['defect_points'], username, r['calculation_factor'],
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
                                cur.execute(
                                    "INSERT INTO users (username, name, password_hash, email) VALUES (%s, %s, %s, %s)",
                                    (new_username, new_name, hashed_password, new_email)
                                )
                                conn.commit()
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

    # --- CONSTRUCTION DE LA SIDEBAR DE HAUT EN BAS ---
    with strl.sidebar:
        if os.path.exists("image_609dcc.png"): 
            strl.image("image_609dcc.png", use_column_width=True)
        strl.markdown("<h2 style='text-align: center; margin-bottom: 0px;'>DRÄXLMAIER</h2>", unsafe_allow_html=True)
        strl.markdown("<p style='text-align: center; color: #94a3b8; font-size: 14px;'>Automotive System Quality</p>", unsafe_allow_html=True)
        
        strl.markdown("---")
        strl.markdown(f"<h3 style='text-align: center; color: #00ffd0;'>Welcome, {name}</h3>", unsafe_allow_html=True)
        strl.markdown(f"<p style='text-align: center; color: #a3a8b4;'>@{username}</p>", unsafe_allow_html=True)
        
        strl.markdown("---")
        strl.markdown("<h4 style='color: #ff4b4b; margin-bottom: 5px;'>⚠️ Danger Zone</h4>", unsafe_allow_html=True)
        confirm_wipe = strl.checkbox("I understand this will erase all quality logs")
        
        if strl.button(" Wipe Database Data", disabled=not confirm_wipe):
            try:
                clear_production_database()
                strl.success(" Database successfully cleared!")
                strl.rerun()
            except Exception as e:
                strl.error(f"Failed to clear database: {str(e)}")
        
        for _ in range(2):
            strl.write("")
            
        strl.markdown("---")
        authenticator.logout(' Log Out', 'sidebar')

    # Instanciation des onglets principaux dans la zone centrale
    tab1, tab2, tab3 = strl.tabs(["DATA INTAKE PORTAL", "QUALITY ANALYTICS REGISTER", "VIEW DASHBOARD"])

try:
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
                    
                    defects = []
                    occurrences = []
                    
                    for h in details:
                        for d in h.get("raw_defects_list", []):
                            defects.append({
                                "drawing_number": h["drawing_number"],
                                "defect_code": d["code"],
                                "penalty_points": d["points"]
                            })
                            
                            occ_found = next((o for o in occurrences if o["defect_code"] == d["code"]), None)
                            if occ_found: 
                                occ_found["total_count"] += 1
                            else: 
                                occurrences.append({
                                    "defect_code": d["code"], 
                                    "total_count": 1
                                })

                    save_to_database(summary, details, defects, occurrences, username)
                    status_text.empty()
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
            dashboard_subtab = strl.radio(
                "Select View:",
                ["Quality Class average per plant", "Defect Code Frequency & Occurrence"],
                horizontal=True
            )
            strl.markdown("---")
            try:
                conn = get_db_connection()
                if dashboard_subtab == "Quality Class average per plant":
                    df_dash = pd.read_sql("SELECT plant, qk_avg FROM public.monthly_summaries", conn)
                    if not df_dash.empty:
                        fig = px.bar(df_dash, x='plant', y='qk_avg', title="QK Average per Plant", color='qk_avg')
                        fig.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font_color="#ffffff",
                            title_font_color="#ffffff"
                        )
                        strl.plotly_chart(fig, use_container_width=True)
                        global_qk_avg = df_dash['qk_avg'].mean()
                        strl.markdown(f"""
                        <div style="background-color: rgba(0, 255, 208, 0.1); border-left: 5px solid #00ffd0; padding: 15px; border-radius: 4px; margin-top: 20px;">
                            <h4 style="margin: 0; color: #ffffff;">Global QK Average (All Plants Combined)</h4>
                            <p style="font-size: 24px; font-weight: bold; color: #00ffd0; margin: 5px 0 0 0;">{global_qk_avg:.2f}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        strl.info("Dashboard awaiting production data...")
                        
                elif dashboard_subtab == "Defect Code Frequency & Occurrence":
                    query_occ = """
                        SELECT s.plant, o.defect_code, o.total_count
                        FROM public.pdf_total_occurrences o
                        JOIN public.monthly_summaries s ON o.summary_id = s.summary_id
                    """
                    df_occ = pd.read_sql(query_occ, conn)
                    if not df_occ.empty:
                        col_chart, col_select = strl.columns([3, 1])
                        with col_select:
                            strl.markdown("<h4 style='color: #00ffd0;'>Plant Selection</h4>", unsafe_allow_html=True)
                            plant_list = sorted(df_occ['plant'].unique())
                            selected_plant = strl.radio("Filter by plant:", plant_list, key="plant_dashboard_filter")
                            
                        with col_chart:
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
    pass