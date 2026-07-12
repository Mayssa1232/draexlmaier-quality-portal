import streamlit as st
import pandas as pd
import sys
import os
import plotly.express as px
import streamlit_authenticator as stauth
import psycopg2
from psycopg2.extras import RealDictCursor
import yaml
from yaml.loader import SafeLoader
import hashlib
import plotly.io as pio
pio.renderers.default = "notebook_connected"
import warnings

# Mute standard pandas DBAPI2 connection warnings in logs
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

# Alias for compatibility with your existing workspace code
strl = st

# 1. PAGE CONFIGURATION (MUST BE ABSOLUTELY FIRST)
st.set_page_config(page_title="DRÄXLMAIER Quality Portal", layout="wide")

# Session State Initialization
if "tabs_initialized" not in st.session_state:
    st.session_state["tabs_initialized"] = False

# --- CONFIGURATION DYNAMIQUE DES CHEMINS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, "..", "backend"))

if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Import des fonctions du pipeline avec gestion d'erreur
try:
    from run_pipeline import extract_dynamic_pdf_data, get_db_connection
except (ModuleNotFoundError, ImportError) as e:
    st.error(f"Erreur de chemin : Impossible de charger les fonctions de 'run_pipeline.py'. Détails : {e}")

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

    /* Style des onglets principaux */
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
    
    /* MODIFICATION DES BOUTONS */
    .stButton>button,
    div[data-testid="stForm"] button[data-testid="baseButton-secondary"] {
        width: 100% !important;
        height: 45px !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        background-color: #12161a !important;
        color: #ffffff !important;
        border: 1px solid #ff4b4b !important;
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
st.markdown(global_design_css, unsafe_allow_html=True)

# --- DYNAMIC USER LOAD FROM NEON DATABASE ---
@st.cache_data(show_spinner=False)
def load_users_from_db():
    auth_dict = {"credentials": {"usernames": {}}}
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT username, name, password_hash, email, role FROM users;")
                rows = cur.fetchall()
                for row in rows:
                    auth_dict["credentials"]["usernames"][row["username"]] = {
                        "name": row["name"],
                        "password": row["password_hash"],
                        "email": row["email"],
                        "role": row.get("role", "user")
                    }
    except Exception as e:
        st.error(f"Database connection error: {e}")
    return auth_dict

auth_dict = load_users_from_db()

# --- SECURE CONFIG & INITIALIZATION FOR AUTHENTICATOR ---
authenticator = stauth.Authenticate(
    credentials=auth_dict["credentials"],
    cookie_name='quality_portal_cookie',
    key='une_cle_de_signature_tres_longue_et_securisee_draexlmaier_2026',
    cookie_expiry_days=30
)

# --- DANGER ZONE DATA CORRECTION FUNCTION ---
def clear_production_database():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("TRUNCATE TABLE public.audit_defects_raw RESTART IDENTITY CASCADE;")
                cur.execute("TRUNCATE TABLE public.pdf_total_occurrences RESTART IDENTITY CASCADE;")
                cur.execute("TRUNCATE TABLE public.harness_audits RESTART IDENTITY CASCADE;")
                cur.execute("TRUNCATE TABLE public.monthly_summaries RESTART IDENTITY CASCADE;")
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e

# --- MULTI-TABLE INJECTION FUNCTION ---
def save_to_database(summary, details, defects_list, occurrences_list, username, file_bytes):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                # 1. Calculate unique MD5 hash from the file bytes
                pdf_hash = hashlib.md5(file_bytes).hexdigest()
                
                # 2. Insert summary only if this exact report/file combination doesn't exist for the plant/supplier
                cur.execute("""
                    INSERT INTO public.monthly_summaries
                    (supplier, plant, country, report_month, report_year, QK_min, QK_avg, QK_max, audits_count, pdf_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
                    ON CONFLICT (plant, supplier, report_month, report_year, pdf_hash) DO NOTHING
                    RETURNING summary_id;
                """, (summary['supplier'], summary['plant'], summary['country'],
                    str(summary['report_month']), str(summary['report_year']),
                    summary['QK_min'], summary['QK_avg'], summary['QK_max'], summary['audits_count'], pdf_hash))
                
                result = cur.fetchone()
                
                # If result is None, it means ON CONFLICT was triggered (Duplicate found)
                if result is None:
                    raise Exception("Duplicate ignored: This specific PDF report has already been processed for this site/plant.")
                
                summary_id = result[0]

                audit_id_map = {}
                for r in details:
                    cur.execute("""
                        INSERT INTO public.harness_audits
                        (summary_id, vehicle_type, drawing_number, part_description, QK_score, defect_count, defect_points, inserted_by, calculation_factor, count_wires, count_contacts, count_components, audit_type)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING audit_id;
                    """, (
                        summary_id, r.get('vehicle_type'), r.get('drawing_number'), r.get('part_description'), 
                        r.get('QK_score'), r.get('defect_count'), r.get('defect_points'), username, 
                        r.get('calculation_factor'), r.get('count_wires'), r.get('count_contacts'), 
                        r.get('count_components'), r.get('audit_type')
                    ))
                    generated_id = cur.fetchone()[0]
                    
                    dn = r.get('drawing_number')
                    if dn:
                        if dn not in audit_id_map:
                            audit_id_map[dn] = []
                        audit_id_map[dn].append(generated_id)

                for d in defects_list:
                    dn_defect = d.get('drawing_number', '')
                    target_audit_id = None
                    
                    for registered_dn, ids in audit_id_map.items():
                        if registered_dn in dn_defect or dn_defect in registered_dn:
                            target_audit_id = ids[0]
                            break
                            
                    if target_audit_id:
                        cur.execute("""
                            INSERT INTO public.audit_defects_raw (audit_id, defect_code, penalty_points) 
                            VALUES (%s, %s, %s);
                        """, (target_audit_id, d.get('defect_code'), d.get('penalty_points')))

                for o in occurrences_list:
                    cur.execute("""
                        INSERT INTO public.pdf_total_occurrences (summary_id, defect_code, total_count) 
                        VALUES (%s, %s, %s);
                    """, (summary_id, o.get('defect_code'), o.get('total_count')))

                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e

# --- WELCOME GATE INTERFACE (LOGIN / REGISTRATION) ---
if not st.session_state.get("authentication_status"):
    st.session_state["tabs_initialized"] = False
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #00ffd0;'>D-DRÄXLMAIER</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>Quality Audit Portal</h3>", unsafe_allow_html=True)
        
        auth_tab1, auth_tab2 = st.tabs([" Sign In", " Create Account"])
        
        with auth_tab1:
            authenticator.login(location='main')
            if st.session_state.get("authentication_status") is False:
                st.error("Invalid username or password.")
            elif st.session_state.get("authentication_status") is None:
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
                            with get_db_connection() as conn:
                                with conn.cursor() as cur:
                                    cur.execute("SELECT username FROM users WHERE username = %s OR email = %s", (new_username, new_email))
                                    if cur.fetchone():
                                        st.error("This username or email is already taken.")
                                    else:
                                        cur.execute(
                                            "INSERT INTO users (username, name, password_hash, email, role) VALUES (%s, %s, %s, %s, 'user')",
                                            (new_username, new_name, hashed_password, new_email)
                                        )
                                        conn.commit()
                                        st.cache_data.clear()  # Evict cached credentials safely
                                        st.success("Account created successfully! You can now log in.")
                                        st.rerun()
                        except Exception as e:
                            st.error(f"Registration failed: {e}")

else:
    name = st.session_state["name"]
    username = st.session_state["username"]
    
    # Secure role mapping from database architecture
    user_data = auth_dict["credentials"]["usernames"].get(username, {})
    st.session_state["role"] = user_data.get('role', 'user')
    st.session_state['user_email'] = user_data.get('email', '')
    
    with strl.sidebar:
        if os.path.exists("image_609dcc.png"): 
            strl.image("image_609dcc.png", use_container_width=True)
        strl.markdown("<h2 style='text-align: center; margin-bottom: 0px;'>DRÄXLMAIER</h2>", unsafe_allow_html=True)
        strl.markdown("<p style='text-align: center; color: #94a3b8; font-size: 14px;'>Automotive System Quality</p>", unsafe_allow_html=True)
        
        strl.markdown("---")
        strl.markdown(f"<h3 style='text-align: center; color: #00ffd0;'>Welcome, {name}</h3>", unsafe_allow_html=True)
        strl.markdown(f"<p style='text-align: center; color: #a3a8b4;'>@{username}</p>", unsafe_allow_html=True)
        
        strl.markdown("---")
        strl.markdown("<h4 style='color: #ff4b4b; margin-bottom: 5px;'>⚠️ Danger Zone</h4>", unsafe_allow_html=True)
        
        if st.session_state.get("role") == "admin":
            confirm_wipe = strl.checkbox("I understand this will erase all quality logs", key="admin_sidebar_wipe_checkbox")
            if strl.button(" Wipe Database Data", disabled=not confirm_wipe):
                try:
                    clear_production_database()
                    strl.success(" Database successfully cleared!")
                    strl.rerun()
                except Exception as e:
                    strl.error(f"Failed to clear database: {str(e)}")
        else:
            strl.warning("🔒 Actions réservées aux administrateurs.")
        
        strl.markdown("---")
        authenticator.logout(' Log Out', 'sidebar')

    tab1, tab2, tab3 = strl.tabs(["DATA INTAKE PORTAL", "QUALITY ANALYTICS REGISTER", "VIEW DASHBOARD"])

# ==============================================================================
# --- PORTAL TABS MANAGEMENTS ---
# ==============================================================================

# --- DATA INTAKE ---
with tab1:
    strl.header("Data Intake Portal")
    
    if "injection_success" in st.session_state:
        strl.success(st.session_state["injection_success"])
        if strl.button("Clear Notification"):
            del st.session_state["injection_success"]
            strl.rerun()

    uploaded_file = strl.file_uploader("Upload Compliance PDF", type=["pdf"])
    if uploaded_file and strl.button(" Inject into Database"):
        try:
            with strl.spinner(" Processing PDF and preparing database injection..."):
                file_bytes = uploaded_file.read() # On lit les bytes une seule fois ici
                summary, details = extract_dynamic_pdf_data(file_bytes)
                
                defects = []
                occurrences = []
                
                for h in details:
                    raw_defects = (
                        h.get("raw_defects_list") or 
                        h.get("defects") or 
                        h.get("defects_list") or []
                    )
                    dn = h.get("drawing_number") or "Unknown"
                    
                    for d in raw_defects:
                        code_defaut = d.get("code") or d.get("defect_code") or d.get("name")
                        points_defaut = d.get("points") or d.get("penalty_points") or 0
                        
                        if code_defaut:
                            defects.append({
                                "drawing_number": dn,
                                "defect_code": code_defaut,
                                "penalty_points": int(points_defaut)
                            })
                            
                            occ_found = next((o for o in occurrences if o["defect_code"] == code_defaut), None)
                            if occ_found: 
                                occ_found["total_count"] += 1
                            else: 
                                occurrences.append({
                                    "defect_code": code_defaut, 
                                    "total_count": 1
                                })

                # Passage explicite de file_bytes en 6ème paramètre
                save_to_database(summary, details, defects, occurrences, username, file_bytes)
            
            st.session_state["injection_success"] = "✅ Data successfully injected into all tables!"
            st.toast("🎉 Injection réussie avec succès !", icon="✅")
            strl.rerun()
            
        except Exception as e:
            strl.error(f"Injection Failed: {str(e)}")

# --- ANALYTICS REGISTER ---
with tab2:
    strl.header("Quality Analytics Register")
    if st.session_state.get("role") == "admin":
        strl.success("🔓 Accès Admin accordé")
        subtab1, subtab2, subtab3, subtab4 = strl.tabs(["Monthly Summaries", "Harness Audits", "Audit Defects", "Occurrences"])

        try:
            # Utilisation directe du context manager natif pour les requêtes Pandas SQL
            with get_db_connection() as conn:
                with subtab1:
                    query1 = "SELECT * FROM public.monthly_summaries;"
                    df1 = pd.read_sql(query1, conn)
                    if not df1.empty:
                        strl.dataframe(df1.drop(columns=['summary_id'], errors='ignore'), use_container_width=True)
                        
                with subtab2:
                    query2 = "SELECT s.plant, h.* FROM public.harness_audits h JOIN public.monthly_summaries s ON h.summary_id = s.summary_id"
                    df2 = pd.read_sql(query2, conn)
                    if not df2.empty:
                        strl.dataframe(df2.drop(columns=['summary_id', 'audit_id'], errors='ignore'), use_container_width=True)
                        
                with subtab3:
                    query3 = "SELECT s.plant, d.* FROM public.audit_defects_raw d JOIN public.harness_audits h ON d.audit_id = h.audit_id JOIN public.monthly_summaries s ON h.summary_id = s.summary_id"
                    df3 = pd.read_sql(query3, conn)
                    if not df3.empty:
                        strl.dataframe(df3.drop(columns=['audit_id'], errors='ignore'), use_container_width=True)
                        
                with subtab4:
                    query4 = "SELECT s.plant, o.* FROM public.pdf_total_occurrences o JOIN public.monthly_summaries s ON o.summary_id = s.summary_id"
                    df4 = pd.read_sql(query4, conn)
                    if not df4.empty:
                        strl.dataframe(df4.drop(columns=['summary_id'], errors='ignore'), use_container_width=True)
                        
        except Exception as e:
            strl.error(f"Error loading registers: {str(e)}")
    else:
        strl.warning("⚠️ Accès restreint. Seuls les administrateurs ont les droits requis.")
            
# --- DASHBOARD ---
with tab3:
    strl.header("Performance Dashboard")
    
    if st.session_state.get("role") == "admin":
        try:
            with get_db_connection() as conn:
                # 1. RÉCUPÉRATION DES MOIS DISPONIBLES (Basé sur la date du PDF)
                query_months = "SELECT DISTINCT TO_CHAR(created_at, 'YYYY-MM') as audit_month FROM public.monthly_summaries ORDER BY audit_month DESC"
                df_months = pd.read_sql(query_months, conn)
                
                if not df_months.empty:
                    available_months = df_months['audit_month'].tolist()
                    
                    # Sélecteur global de mois tout en haut
                    selected_month = strl.selectbox("📅 Select Audit Month:", available_months, key="global_dashboard_month")
                    strl.markdown("---")
                    
                    # Onglets radio
                    dashboard_subtab = strl.radio("Select View:", ["Quality Class average per plant", "Defect Code Frequency & Occurrence"], horizontal=True)
                    strl.markdown("---")
                    
                    # --- VUE 1 : QUALITY CLASS AVERAGE PER PLANT ---
                    if dashboard_subtab == "Quality Class average per plant":
                        query_qk = f"SELECT plant, qk_avg FROM public.monthly_summaries WHERE TO_CHAR(created_at, 'YYYY-MM') = '{selected_month}'"
                        df_dash = pd.read_sql(query_qk, conn)
                        
                        if not df_dash.empty:
                            fig = px.bar(df_dash, x='plant', y='qk_avg', title=f"QK Average per Plant ({selected_month})", color='qk_avg')
                            fig.update_layout(
                                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                font_color="#ffffff", title_font_color="#ffffff",
                                xaxis=dict(showgrid=False, categoryorder='total descending'),
                                yaxis=dict(gridcolor='rgba(255,255,255,0.1)')
                            )
                            strl.plotly_chart(fig, width="stretch")
                            
                            # Calcul de la moyenne pour CE mois précis
                            global_qk_avg = df_dash['qk_avg'].mean()
                            strl.markdown(f"""
                            <div style="background-color: rgba(0, 255, 208, 0.1); border-left: 5px solid #00ffd0; padding: 15px; border-radius: 4px; margin-top: 20px;">
                                <h4 style="margin: 0; color: #ffffff;">Global QK Average for {selected_month} (All Plants Combined)</h4>
                                <p style="font-size: 24px; font-weight: bold; color: #00ffd0; margin: 5px 0 0 0;">{global_qk_avg:.2f}%</p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            strl.info(f"No production data found for the month: {selected_month}")
                            
                    # --- VUE 2 : DEFECT CODE FREQUENCY & OCCURRENCE ---
                    elif dashboard_subtab == "Defect Code Frequency & Occurrence":
                        query_occ = f"""
                            SELECT s.plant, o.defect_code, o.total_count 
                            FROM public.pdf_total_occurrences o 
                            JOIN public.monthly_summaries s ON o.summary_id = s.summary_id
                            WHERE TO_CHAR(s.created_at, 'YYYY-MM') = '{selected_month}'
                        """
                        df_occ = pd.read_sql(query_occ, conn)
                        
                        if not df_occ.empty:
                            col_chart, col_select = strl.columns([3, 1])
                            
                            with col_select:
                                strl.markdown("<h4 style='color: #00ffd0;'>Plant Selection</h4>", unsafe_allow_html=True)
                                plant_list = ["All Plants"] + sorted(df_occ['plant'].unique())
                                selected_plant = strl.radio("Filter by plant:", plant_list, key="plant_dashboard_filter")
                                
                            with col_chart:
                                if selected_plant == "All Plants":
                                    df_filtered = df_occ.groupby('defect_code')['total_count'].sum().reset_index()
                                    chart_title = f"Total Occurrences per Defect Code - Combined Plants ({selected_month})"
                                else:
                                    df_filtered = df_occ[df_occ['plant'] == selected_plant]
                                    chart_title = f"Occurrences per Defect Code - Plant: {selected_plant} ({selected_month})"
                                
                                if not df_filtered.empty:
                                    fig_occ = px.bar(
                                        df_filtered, x='defect_code', y='total_count', title=chart_title,
                                        labels={'defect_code': 'Defect Code', 'total_count': 'Occurrence Count'},
                                        color='total_count', color_continuous_scale='Viridis', text_auto=True
                                    )
                                    fig_occ.update_layout(
                                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                        font_color="#ffffff", title_font_color="#ffffff",
                                        xaxis=dict(showgrid=False, categoryorder='total descending'),
                                        yaxis=dict(gridcolor='rgba(255,255,255,0.1)')
                                    )
                                    strl.plotly_chart(fig_occ, width="stretch")
                                else:
                                    strl.warning(f"No defects logged for plant: {selected_plant} in {selected_month}.")
                        else:
                            strl.info(f"No occurrence data available for {selected_month}.")
                else:
                    strl.info("Dashboard awaiting database records...")
        except Exception as e:
            strl.error(f"Dashboard Load Error: {str(e)}")
    else:
        strl.warning("⚠️ Access restricted. Only administrators have the required rights.")