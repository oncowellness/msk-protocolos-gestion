import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Any

# ─── CONFIG PÁGINA ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MSK · Gestión Oncológica",
    page_icon="🎗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a8e 100%);
        padding: 1.2rem; border-radius: 12px; color: white; text-align: center;
        margin-bottom: 0.5rem;
    }
    .metric-card h3 { font-size: 0.85rem; opacity: 0.85; margin-bottom: 0.3rem; }
    .metric-card h2 { font-size: 1.6rem; font-weight: 700; margin: 0; }
    .phase-header {
        background: linear-gradient(90deg, #1e3a5f, #2d5a8e);
        color: white; padding: 1rem 1.5rem; border-radius: 10px; margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ─── CARGA DE DATOS ───────────────────────────────────────────────────────────
DATA_DIR = Path("data")

@st.cache_data
def load_journey() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "JOURNEY_x_FASE.csv", header=None)


@st.cache_data
def load_paquetes() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "PAQUETES_CLINICOS.csv", skiprows=1)
    df.columns = df.columns.str.strip()
    df = df[df["Código"].notna() & df["Código"].astype(str).str.startswith("PC")]
    return df.reset_index(drop=True)


@st.cache_data
def load_catalogo() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "CATALOGO_PROGRAMAS.csv", skiprows=1)
    df.columns = df.columns.str.strip()
    df = df[
        df["Código"].notna()
        & ~df["Código"].astype(str).str.startswith("←")
        & df["Código"].astype(str).str.strip().ne("")
    ]
    return df.reset_index(drop=True)


@st.cache_data
def load_financiero() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "PLANIFICACION_FINANCIERA.csv", skiprows=1)
    df.columns = df.columns.str.strip()
    df = df[
        df["Código"].notna()
        & ~df["Código"].astype(str).str.startswith("←")
        & ~df["Código"].astype(str).str.startswith(",")
        & df["Código"].astype(str).str.strip().ne("")
    ]
    num_cols = [
        "Precio/Ses (€)", "Coste/Ses (€)", "Margen/Ses (€)", "Margen %",
        "Ses/Pac Tipo", "Ingreso/Pac (€)", "Pac/Año Est.",
        "Ingresos Anuales (€)", "Costes Anuales (€)", "Beneficio Bruto (€)",
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.reset_index(drop=True)


@st.cache_data
def load_kpis() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "INDICADORES_KPIs.csv", skiprows=1)
    df.columns = df.columns.str.strip()
    return df[df["Código Programa"].notna()].reset_index(drop=True)

# ─── CONSTANTES ───────────────────────────────────────────────────────────────
PHASES = {
    "F1": {"label": "F1 — Diagnóstico y decisiones iniciales", "col": 1, "pack": "PC-01", "emoji": "⚠️"},
    "F2": {"label": "F2 — Prehabilitación / Preparación",      "col": 2, "pack": "PC-02", "emoji": "🛡️"},
    "F3": {"label": "F3 — Tratamiento activo (Cx/QT/RT)",      "col": 3, "pack": "PC-03", "emoji": "💧"},
    "F4": {"label": "F4 — Rehabilitación temprana (0-12m)",    "col": 4, "pack": "PC-04", "emoji": "🌱"},
    "F5": {"label": "F5 — Supervivencia y mantenimiento",      "col": 5, "pack": "PC-04", "emoji": "✨"},
    "F6": {"label": "F6 — Recaída / Progresión",               "col": 6, "pack": "PC-05", "emoji": "💥"},
    "F7": {"label": "F7-F8 — Enf. avanzada / Terminal / Duelo","col": 7, "pack": "PC-05", "emoji": "🕊️"},
}

JOURNEY_ROWS = {
    "Touchpoints Clínicos":    2,
    "Touchpoints No Clínicos": 3,
    "Mind State":              6,
    "Pain Points":             7,
    "Necesidades de Soporte":  8,
    "Programas Asignados":     9,
}

MARKETING_TONES = {
    "SHOCK":      ("Empática y contenedora",
                   "Mensajes cortos, directos y tranquilizadores. Evita el exceso de información. "
                   "Usa 'no estás solo/a', 'estamos contigo'. Canal: llamada personal o SMS breve."),
    "SEGURIDAD":  ("Proactiva y capacitadora",
                   "Destaca el control activo del paciente. Usa 'prepárate', 'lidera tu recuperación'. "
                   "Infografías y vídeos cortos. Canal: email + WhatsApp + RRSS."),
    "VULNERABLE": ("Contenedora y simple",
                   "Información fraccionada, sin sobrecargar. Valida el esfuerzo. "
                   "Usa 'día a día', 'pequeños pasos'. Canal: app push + email semanal."),
    "AGOTADO":    ("Validadora y esperanzadora",
                   "Reconoce el cansancio. Celebra logros mínimos. Usa 'lo estás haciendo bien'. "
                   "Canal: comunidad digital + mensaje de coach."),
    "ALIVIO":     ("Celebrativa y realista",
                   "Reconoce el hito. Gestiona expectativas sobre secuelas. "
                   "Usa 'nuevo capítulo', 'a tu ritmo'. Canal: email + talleres grupales."),
    "CONFIANZA":  ("Comunitaria y preventiva",
                   "Invita a la comunidad de supervivientes. Foco en hábitos saludables. "
                   "Usa 'inspira a otros', 'cuídate para siempre'. Canal: RRSS + eventos."),
    "PERDIDO":    ("No invasiva y flexible",
                   "Mínima fricción, máxima escucha. Ofrece opciones, no imposiciones. "
                   "Usa 'cuando quieras', 'aquí estamos'. Canal: llamada del psicólogo."),
    "CARGA":      ("Íntima, espiritual y dignificante",
                   "Respeta los silencios. Foco en legado y despedida. "
                   "Usa 'lo que importa eres tú', 'tu historia importa'. Canal: visita domiciliaria."),
}


def get_journey_value(journey_df: pd.DataFrame, col_idx: int, row_idx: int) -> str:
    try:
        val = journey_df.iloc[row_idx, col_idx]
        return str(val) if pd.notna(val) else "—"
    except (IndexError, KeyError):
        return "—"


def extract_program_codes(text: str) -> List[str]:
    return re.findall(r"[A-Z]{2,4}-\d{2,3}", str(text))


def discipline_from_code(code: str) -> str:
    prefix = str(code).split("-")[0]
    mapping = {
        "FX": "Fisioterapia", "PS": "Psicología", "NU": "Nutrición",
        "EO": "Estética Oncológica", "PI": "Pack Integral", "TS": "Trabajo Social",
        "SX": "Sexología / S. Pélvico", "PA": "Paliativos / Dolor",
        "ED": "Educación", "TO": "Terapia Ocupacional",
    }
    return mapping.get(prefix, prefix)


def marketing_tone(mindstate: str) -> Tuple[str, str]:
    ms = mindstate.upper()
    for key, val in MARKETING_TONES.items():
        if key in ms:
            return val
    return ("Adaptativa", "Ajusta el tono según la evolución del paciente en esta fase.")


# ═══════════════════════════════════════════════════════════════════════════════
#   MÓDULO A — GENERADOR DE PROTOCOLOS CLÍNICOS (F1-F8)
# ═══════════════════════════════════════════════════════════════════════════════
def render_module_a(journey_df: pd.DataFrame, paquetes_df: pd.DataFrame, catalogo_df: pd.DataFrame):
    """Renderiza el Generador de Protocolos Clínicos."""
    st.markdown("## 🗂️ Módulo A — Generador de Protocolos Clínicos")
    st.caption("Selecciona una fase del Journey del paciente para desplegar el protocolo integrado.")

    phase_keys   = list(PHASES.keys())
    phase_labels = [f"{PHASES[k]['emoji']}  {PHASES[k]['label']}" for k in phase_keys]
    sel_idx      = st.selectbox(
        "Fase del Journey",
        range(len(phase_labels)),
        format_func=lambda i: phase_labels[i],
        index=phase_keys.index("F3"),
    )
    sel_phase = phase_keys[sel_idx]
    phase_info = PHASES[sel_phase]
    col_idx    = phase_info["col"]

    # Datos del journey
    mind_state     = get_journey_value(journey_df, col_idx, JOURNEY_ROWS["Mind State"])
    pain_points    = get_journey_value(journey_df, col_idx, JOURNEY_ROWS["Pain Points"])
    touchpoints_c  = get_journey_value(journey_df, col_idx, JOURNEY_ROWS["Touchpoints Clínicos"])
    touchpoints_nc = get_journey_value(journey_df, col_idx, JOURNEY_ROWS["Touchpoints No Clínicos"])
    necesidades    = get_journey_value(journey_df, col_idx, JOURNEY_ROWS["Necesidades de Soporte"])
    programas_raw  = get_journey_value(journey_df, col_idx, JOURNEY_ROWS["Programas Asignados"])

    st.markdown(
        f'<div class="phase-header">'
        f'<h2 style="margin:0">{phase_info["emoji"]}  {phase_info["label"]}</h2>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Columnas de journey info
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🧠 Mind State del Paciente")
        st.info(mind_state)
        st.markdown("#### 🩺 Touchpoints Clínicos")
        st.write(touchpoints_c)
    with c2:
        st.markdown("#### ⚡ Pain Points Principales")
        st.warning(pain_points)
        st.markdown("#### 🤝 Touchpoints No Clínicos")
        st.write(touchpoints_nc)

    st.markdown("#### 🎯 Necesidades de Soporte")
    st.write(necesidades)

    # ── Paquete clínico asociado ────────────────────────────────────────────
    pack_code = phase_info["pack"]
    pack_mask = paquetes_df["Código"] == pack_code
    pack_rows = paquetes_df[pack_mask]

    st.divider()
    st.markdown(f"### 📦 Paquete Clínico: **{pack_code}**")

    if not pack_rows.empty:
        pr = pack_rows.iloc[0]
        pack_name       = pr.get("Nombre del Paquete", "—")
        pack_pvp        = float(pr.get("PVP Pack (€)", 0) or 0)
        pack_cost       = float(pr.get("Coste Est. (€)", 0) or 0)
        pack_margin     = float(pr.get("Margen %", 0) or 0)
        pack_sessions   = pr.get("Sesiones Totales", "—")
        pack_duration   = pr.get("Duración Tipo", "—")
        pack_progs_raw  = str(pr.get("Programas Incluidos (códigos)", ""))
        pack_products   = pr.get("Productos Bundle", "—")
        pack_need       = pr.get("Necesidad Clínica Principal", "—")

        m1, m2, m3, m4 = st.columns(4)
        for col, label, value in [
            (m1, "PVP Pack", f"€{pack_pvp:,.0f}"),
            (m2, "Coste Est.", f"€{pack_cost:,.0f}"),
            (m3, "Margen Bruto", f"€{pack_pvp - pack_cost:,.0f}"),
            (m4, "Margen %", f"{pack_margin * 100:.1f}%"),
        ]:
            col.markdown(
                f'<div class="metric-card"><h3>{label}</h3><h2>{value}</h2></div>',
                unsafe_allow_html=True)

        st.markdown(f"**{pack_name}** — *{pack_need}*")
        st.markdown(f"⏱ Duración: **{pack_duration}** · Sesiones: **{pack_sessions}**")
        st.markdown(f"🛍️ Productos Bundle: {pack_products}")

        # Programas del paquete
        prog_codes = extract_program_codes(pack_progs_raw) or extract_program_codes(programas_raw)
        st.markdown(f"#### 🔬 Intervenciones Incluidas ({len(prog_codes)} programas)")

        prog_details = catalogo_df[
            catalogo_df["Código"].astype(str).str.strip().isin(prog_codes)
        ]

        # Agrupar por disciplina
        disc_groups: Dict[str, List[str]] = {}
        for code in prog_codes:
            disc_groups.setdefault(discipline_from_code(code), []).append(code)

        if disc_groups:
            tabs = st.tabs(list(disc_groups.keys()))
            for tab, disc in zip(tabs, disc_groups.keys()):
                with tab:
                    for code in disc_groups[disc]:
                        row = prog_details[prog_details["Código"].astype(str).str.strip() == code]
                        if not row.empty:
                            r = row.iloc[0]
                            with st.expander(f"**{code}** — {r.get('Nombre del Programa', '—')}"):
                                cc1, cc2 = st.columns(2)
                                with cc1:
                                    st.markdown(f"**Objetivos:** {r.get('Objetivos Principales','—')}")
                                    st.markdown(f"**Frecuencia:** {r.get('Frecuencia Sesiones','—')}")
                                    st.markdown(f"**Sesiones:** {r.get('Nº Sesiones Tipo','—')}")
                                    st.markdown(f"**Duración:** {r.get('Duración Programa (sem)','—')} sem")
                                with cc2:
                                    st.markdown(f"**Modalidad:** {r.get('Modalidad Producto','—')}")
                                    st.markdown(f"**Precio/sesión:** €{r.get('Precio/Sesión (€)','—')}")
                                    st.markdown(f"**Paciente diana:** {r.get('Perfil Paciente Diana','—')}")
                                    st.markdown(f"**Mind State:** {r.get('Mind State Paciente','—')}")
                        else:
                            st.markdown(f"**{code}** — datos no encontrados en catálogo")
                            st.text_area(
                                f"Descripción manual para {code}:",
                                key=f"manual_{code}",
                                placeholder="Introduce la descripción de esta intervención...",
                            )
    else:
        st.warning(f"No se encontraron datos para el paquete {pack_code}.")


# ═══════════════════════════════════════════════════════════════════════════════
#   MÓDULO B — THE BRIDGE (TRADUCTOR DEPARTAMENTAL)
# ═══════════════════════════════════════════════════════════════════════════════
def render_module_b(paquetes_df: pd.DataFrame, financiero_df: pd.DataFrame, kpis_df: pd.DataFrame):
    """Renderiza el módulo The Bridge."""
    st.markdown("## 🌉 Módulo B — The Bridge")
    st.caption("Traduce un protocolo clínico al lenguaje de cada departamento.")

    pack_options = paquetes_df["Código"].tolist()
    pack_labels  = {
        r["Código"]: f"{r['Código']} — {r.get('Nombre del Paquete','')}"
        for _, r in paquetes_df.iterrows()
    }
    default_pack = "PC-03" if "PC-03" in pack_options else pack_options[0]
    sel_pack = st.selectbox(
        "Paquete Clínico",
        pack_options,
        format_func=lambda c: pack_labels.get(c, c),
        index=pack_options.index(default_pack),
    )

    pr = paquetes_df[paquetes_df["Código"] == sel_pack].iloc[0]
    pack_name      = pr.get("Nombre del Paquete", "—")
    pack_fase      = pr.get("Fase(s) Journey", "—")
    pack_mind      = str(pr.get("Mind State del Paciente", "—"))
    pack_need      = pr.get("Necesidad Clínica Principal", "—")
    pack_pvp       = float(pr.get("PVP Pack (€)", 0) or 0)
    pack_cost      = float(pr.get("Coste Est. (€)", 0) or 0)
    pack_margin_pct = float(pr.get("Margen %", 0) or 0)
    pack_sessions  = pr.get("Sesiones Totales", "—")
    pack_progs_raw = str(pr.get("Programas Incluidos (códigos)", ""))
    pack_products  = pr.get("Productos Bundle", "—")
    prog_codes     = extract_program_codes(pack_progs_raw)

    st.markdown(
        f'<div class="phase-header">'
        f'<strong>{sel_pack} · {pack_name}</strong>&nbsp;|&nbsp;'
        f'Fase: {str(pack_fase).split(chr(10))[0]}&nbsp;|&nbsp;'
        f'Sesiones: {pack_sessions}'
        f'</div>',
        unsafe_allow_html=True,
    )

    tab_fin, tab_mkt, tab_ops = st.tabs(["💰 Finanzas", "📣 Marketing", "⚙️ Operaciones"])

    # ─── FINANZAS ─────────────────────────────────────────────────────────
    with tab_fin:
        st.markdown("### 💰 Análisis Financiero del Paquete")

        fin_rows = financiero_df[
            financiero_df["Código"].astype(str).str.strip().isin(prog_codes)
        ].copy()

        if not fin_rows.empty:
            fin_rows["Coste Total Prog"]   = fin_rows["Coste/Ses (€)"].fillna(0) * fin_rows["Ses/Pac Tipo"].fillna(0)
            fin_rows["Ingreso Total Prog"] = fin_rows["Precio/Ses (€)"].fillna(0) * fin_rows["Ses/Pac Tipo"].fillna(0)

        margen_bruto = pack_pvp - pack_cost
        margen_pct   = margen_bruto / pack_pvp * 100 if pack_pvp else 0

        c1, c2, c3, c4 = st.columns(4)
        for col, label, value in [
            (c1, "Precio Pack",     f"€{pack_pvp:,.0f}"),
            (c2, "Coste Estimado",  f"€{pack_cost:,.0f}"),
            (c3, "Margen Bruto",    f"€{margen_bruto:,.0f}"),
            (c4, "Margen %",        f"{margen_pct:.1f}%"),
        ]:
            col.markdown(
                f'<div class="metric-card"><h3>{label}</h3><h2>{value}</h2></div>',
                unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background:#f0f9ff;border:1px solid #0ea5e9;border-radius:8px;
                    padding:1rem;margin:1rem 0;text-align:center;font-size:1.1rem">
            💳 <strong>€{pack_pvp:,.0f}</strong>&nbsp;(precio pack)
            &nbsp;−&nbsp;
            💸 <strong>€{pack_cost:,.0f}</strong>&nbsp;(coste)
            &nbsp;=&nbsp;
            ✅ <strong style="color:#065f46">€{margen_bruto:,.0f}</strong>&nbsp;margen bruto
            &nbsp;(<strong>{margen_pct:.1f}%</strong>)
        </div>
        """, unsafe_allow_html=True)

        if not fin_rows.empty:
            st.markdown("#### Desglose por Programa")
            cols_show = [c for c in ["Código", "Programa", "Precio/Ses (€)", "Coste/Ses (€)",
                                     "Margen/Ses (€)", "Ses/Pac Tipo", "Margen %"] if c in fin_rows.columns]
            show = fin_rows[cols_show].copy()
            if "Margen %" in show.columns:
                show["Margen %"] = (show["Margen %"] * 100).round(1).astype(str) + "%"
            st.dataframe(show, use_container_width=True, hide_index=True)

            # Gráfico ingresos vs costes por programa
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Ingreso (€)", x=fin_rows["Código"].astype(str),
                y=fin_rows["Ingreso Total Prog"], marker_color="#1d4ed8"))
            fig.add_trace(go.Bar(
                name="Coste (€)", x=fin_rows["Código"].astype(str),
                y=fin_rows["Coste Total Prog"], marker_color="#ef4444"))
            fig.update_layout(
                title="Ingresos vs Costes por Programa (sesiones × precio)",
                barmode="group", height=360, plot_bgcolor="white",
                xaxis_title="Código", yaxis_title="€")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No se encontraron datos financieros individuales. Ajusta manualmente:")
            pvp_m  = st.number_input("Precio Pack (€):", value=pack_pvp)
            cost_m = st.number_input("Coste Total (€):", value=pack_cost)
            margen_m = pvp_m - cost_m
            st.success(f"Margen: €{margen_m:,.0f} ({margen_m/pvp_m*100:.1f}%)" if pvp_m else "")

    # ─── MARKETING ────────────────────────────────────────────────────────
    with tab_mkt:
        st.markdown("### 📣 Estrategia de Comunicación")

        tone_name, tone_desc = marketing_tone(pack_mind)

        st.markdown("#### 🧠 Mind State de la Fase")
        st.info(pack_mind)

        st.markdown("#### ⚡ Pain Points a Comunicar")
        st.warning(pack_need)

        st.markdown(f"#### 🎙️ Tono Recomendado: **{tone_name}**")
        st.success(tone_desc)

        st.markdown("#### ✉️ Mensajes Clave Sugeridos")
        disc_list = list({discipline_from_code(c) for c in prog_codes})
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**🏥 Mensaje Clínico**")
            st.markdown(
                f'*"{pack_name} te ofrece un equipo integrado de '
                f'{", ".join(disc_list[:3])} diseñado para tu momento."*'
            )
        with c2:
            st.markdown("**💬 Mensaje Emocional**")
            fase_label = str(pack_fase).split("\n")[0]
            st.markdown(
                f'*"Cada etapa es diferente. En {fase_label} '
                f'sabemos exactamente lo que necesitas."*'
            )
        with c3:
            st.markdown("**📊 Mensaje de Valor**")
            ses_str = str(pack_sessions)
            st.markdown(
                f'*"{ses_str} sesiones especializadas por solo €{pack_pvp:,.0f}. '
                f'Invierte en tu recuperación."*'
            )

        st.markdown("#### 📡 Canales Recomendados")
        canales = [
            ("📧", "Email personalizado", "Segmentado por fase del paciente"),
            ("📱", "WhatsApp / SMS",       "Recordatorios y seguimiento"),
            ("🌐", "RRSS Orgánicas",       "Contenido educativo y testimonios"),
            ("👨‍⚕️", "Prescripción médica",  "Derivación directa del oncólogo"),
        ]
        for col, (icon, canal, desc) in zip(st.columns(4), canales):
            col.markdown(f"**{icon} {canal}**")
            col.caption(desc)

        st.markdown("#### ✏️ Notas de Campaña (input manual)")
        st.text_area(
            "Directrices específicas:",
            placeholder="Ej: Campaña de septiembre — back to school para supervivientes...",
            key="mkt_notes", height=100,
        )

    # ─── OPERACIONES ──────────────────────────────────────────────────────
    with tab_ops:
        st.markdown("### ⚙️ KPIs Operacionales · PROMs / PREMs")

        kpi_mask = kpis_df["Código Programa"].astype(str).apply(
            lambda x: any(c in x for c in prog_codes)
        )
        rel_kpis = kpis_df[kpi_mask] if kpi_mask.any() else kpis_df

        st.caption(f"{len(rel_kpis)} registros de indicadores para este paquete.")

        for _, kr in rel_kpis.iterrows():
            prog_code = kr.get("Código Programa", "—")
            prog_name = kr.get("Programa", "—")
            proms = kr.get("PROMs (Patient-Reported Outcomes)", "—")
            prems = kr.get("PREMs (Patient-Reported Experience)", "—")
            clin  = kr.get("Indicadores Clínicos", "—")
            uso   = kr.get("Indicadores Uso Servicios", "—")
            freq  = kr.get("Frecuencia Medición", "—")
            resp  = kr.get("Responsable Medición", "—")

            with st.expander(f"**{prog_code}** — {prog_name}"):
                k1, k2 = st.columns(2)
                with k1:
                    st.markdown("**📋 PROMs**")
                    st.write(proms)
                    st.markdown("**🏥 Indicadores Clínicos**")
                    st.write(clin)
                with k2:
                    st.markdown("**⭐ PREMs**")
                    st.write(prems)
                    st.markdown("**📊 Uso de Servicios**")
                    st.write(uso)
                st.markdown(f"🗓️ Frecuencia: **{freq}** · 👤 Responsable: **{resp}**")

        # Tabla resumen
        st.divider()
        st.markdown("#### Resumen")
        summary_kpi = rel_kpis[["Código Programa", "Programa",
                                 "Frecuencia Medición", "Responsable Medición"]].copy()
        summary_kpi.columns = ["Código", "Programa", "Frecuencia", "Responsable"]
        st.dataframe(summary_kpi, use_container_width=True, hide_index=True)

        st.markdown("#### ➕ KPI adicional (input manual)")
        kc1, kc2, kc3 = st.columns(3)
        kc1.text_input("Nombre KPI:", placeholder="Ej: Tasa retención 3m", key="kpi_name")
        kc2.text_input("Objetivo:", placeholder="Ej: ≥ 80%", key="kpi_target")
        kc3.text_input("Responsable:", placeholder="Ej: Coordinador", key="kpi_owner")


# ═══════════════════════════════════════════════════════════════════════════════
#   MÓDULO C — DASHBOARD DE CONTROL DE GESTIÓN
# ═══════════════════════════════════════════════════════════════════════════════
def render_module_c(financiero_df: pd.DataFrame, paquetes_df: pd.DataFrame):
    """Renderiza el Dashboard de Control de Gestión."""
    st.markdown("## 📊 Módulo C — Dashboard de Control de Gestión")
    st.caption("Vista ejecutiva de la cartera de programas oncológicos.")

    # KPIs globales (excluye packs PI para no duplicar)
    fin_base = financiero_df[~financiero_df["Código"].astype(str).str.startswith("PI")].copy()

    total_ingresos  = fin_base["Ingresos Anuales (€)"].fillna(0).sum()
    total_costes    = fin_base["Costes Anuales (€)"].fillna(0).sum()
    total_beneficio = fin_base["Beneficio Bruto (€)"].fillna(0).sum()
    margen_medio    = total_beneficio / total_ingresos * 100 if total_ingresos else 0
    total_pacientes = fin_base["Pac/Año Est."].fillna(0).sum()
    total_progs     = len(fin_base)

    c = st.columns(5)
    for col, label, value in [
        (c[0], "Programas Activos",  f"{total_progs}"),
        (c[1], "Ingresos Anuales",   f"€{total_ingresos/1e6:.2f}M"),
        (c[2], "Costes Anuales",     f"€{total_costes/1e6:.2f}M"),
        (c[3], "Beneficio Bruto",    f"€{total_beneficio/1e6:.2f}M"),
        (c[4], "Margen Medio",       f"{margen_medio:.1f}%"),
    ]:
        col.markdown(
            f'<div class="metric-card"><h3>{label}</h3><h2>{value}</h2></div>',
            unsafe_allow_html=True)

    st.divider()

    # Agrupación por disciplina
    fin_base["Disciplina"] = fin_base["Código"].astype(str).apply(discipline_from_code)
    by_disc = (
        fin_base.groupby("Disciplina")
        .agg(
            Ingresos=("Ingresos Anuales (€)", "sum"),
            Beneficio=("Beneficio Bruto (€)", "sum"),
            Programas=("Código", "count"),
            Pacientes=("Pac/Año Est.", "sum"),
        )
        .reset_index()
        .sort_values("Ingresos", ascending=False)
    )
    by_disc["Margen_pct"] = (by_disc["Beneficio"] / by_disc["Ingresos"] * 100).round(1)

    g1, g2 = st.columns(2)

    with g1:
        st.markdown("#### Distribución de Ingresos por Disciplina")
        fig_pie = px.pie(
            by_disc, values="Ingresos", names="Disciplina",
            color_discrete_sequence=px.colors.qualitative.Set2, hole=0.4,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(height=380, showlegend=False, margin=dict(t=20, b=20, l=10, r=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with g2:
        st.markdown("#### Ingresos Anuales por Disciplina (€)")
        fig_hbar = px.bar(
            by_disc.sort_values("Ingresos"),
            x="Ingresos", y="Disciplina", orientation="h",
            color="Margen_pct", color_continuous_scale="Blues",
            text="Ingresos",
        )
        fig_hbar.update_traces(texttemplate="€%{text:,.0f}", textposition="outside")
        fig_hbar.update_layout(
            height=380, plot_bgcolor="white",
            xaxis_title="€", yaxis_title="",
            coloraxis_colorbar=dict(title="Margen %"),
            margin=dict(t=20, b=20, l=10, r=120))
        st.plotly_chart(fig_hbar, use_container_width=True)

    g3, g4 = st.columns(2)

    with g3:
        st.markdown("#### Precio vs Coste por Paquete Clínico")
        pack_fin = paquetes_df.copy()
        pack_fin["PVP Pack (€)"]   = pd.to_numeric(pack_fin["PVP Pack (€)"], errors="coerce").fillna(0)
        pack_fin["Coste Est. (€)"] = pd.to_numeric(pack_fin["Coste Est. (€)"], errors="coerce").fillna(0)
        pack_fin["Margen Bruto"]   = pack_fin["PVP Pack (€)"] - pack_fin["Coste Est. (€)"]

        fig_pack = go.Figure()
        fig_pack.add_trace(go.Bar(
            name="Precio (€)", x=pack_fin["Código"], y=pack_fin["PVP Pack (€)"],
            marker_color="#1d4ed8", text=pack_fin["PVP Pack (€)"].apply(lambda v: f"€{v:,.0f}"),
            textposition="outside"))
        fig_pack.add_trace(go.Bar(
            name="Coste (€)", x=pack_fin["Código"], y=pack_fin["Coste Est. (€)"],
            marker_color="#ef4444"))
        fig_pack.add_trace(go.Bar(
            name="Margen (€)", x=pack_fin["Código"], y=pack_fin["Margen Bruto"],
            marker_color="#22c55e"))
        fig_pack.update_layout(
            barmode="group", height=360, plot_bgcolor="white",
            yaxis_title="€", xaxis_title="Paquete",
            legend=dict(orientation="h", y=-0.18),
            margin=dict(t=20, b=40))
        st.plotly_chart(fig_pack, use_container_width=True)

    with g4:
        st.markdown("#### Pacientes Estimados / Año por Disciplina")
        fig_pac = px.bar(
            by_disc.sort_values("Pacientes", ascending=False),
            x="Disciplina", y="Pacientes",
            color="Disciplina", color_discrete_sequence=px.colors.qualitative.Set2,
            text="Pacientes",
        )
        fig_pac.update_traces(textposition="outside")
        fig_pac.update_layout(
            height=360, plot_bgcolor="white", showlegend=False,
            xaxis_title="", yaxis_title="Pacientes/año",
            margin=dict(t=20, b=80))
        fig_pac.update_xaxes(tickangle=-30)
        st.plotly_chart(fig_pac, use_container_width=True)

    # Tabla resumen por disciplina
    st.divider()
    st.markdown("#### 📋 Resumen de Cartera por Disciplina")
    disc_table = by_disc.copy()
    disc_table["Ingresos"]   = disc_table["Ingresos"].apply(lambda v: f"€{v:,.0f}")
    disc_table["Beneficio"]  = disc_table["Beneficio"].apply(lambda v: f"€{v:,.0f}")
    disc_table["Pacientes"]  = disc_table["Pacientes"].apply(lambda v: f"{int(v):,}")
    disc_table["Margen_pct"] = disc_table["Margen_pct"].apply(lambda v: f"{v:.1f}%")
    disc_table.columns       = ["Disciplina", "Ingresos Anuales", "Beneficio Bruto",
                                 "Nº Programas", "Pacientes/Año", "Margen %"]
    st.dataframe(disc_table, use_container_width=True, hide_index=True)

    # Top 5 programas por beneficio
    st.markdown("#### 🏆 Top 5 Programas por Beneficio Bruto")
    top5 = (
        fin_base[["Código", "Programa", "Ingresos Anuales (€)", "Beneficio Bruto (€)", "Margen %"]]
        .sort_values("Beneficio Bruto (€)", ascending=False)
        .head(5)
        .copy()
    )
    top5["Ingresos Anuales (€)"] = top5["Ingresos Anuales (€)"].apply(lambda v: f"€{v:,.0f}")
    top5["Beneficio Bruto (€)"]  = top5["Beneficio Bruto (€)"].apply(lambda v: f"€{v:,.0f}")
    top5["Margen %"]             = top5["Margen %"].apply(
        lambda v: f"{v * 100:.1f}%" if pd.notna(v) and v < 1 else f"{v:.1f}%" if pd.notna(v) else "—"
    )
    st.dataframe(top5, use_container_width=True, hide_index=True)


# ─── MAIN APP LOGIC ───────────────────────────────────────────────────────────
def main():
    # 1. Autenticación
    config_path = Path("config.yaml")
    if not config_path.exists():
        st.error("❌ Archivo de configuración 'config.yaml' no encontrado.")
        st.stop()

    with open(config_path) as f:
        config = yaml.load(f, Loader=SafeLoader)

    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )

    # Login — API compatible con streamlit-authenticator >= 0.3
    result = authenticator.login(location="main")
    if result is not None:
        name, authentication_status, username = result
    else:
        name = st.session_state.get("name")
        authentication_status = st.session_state.get("authentication_status")
        username = st.session_state.get("username")

    if authentication_status is False:
        st.error("Usuario o contraseña incorrectos")
        st.stop()
    elif authentication_status is None:
        st.markdown("## 🎗️ MSK · Gestión Oncológica Integral")
        st.info("Por favor, introduce tus credenciales para acceder al panel de dirección.")
        st.stop()

    # 2. Sidebar y Navegación
    with st.sidebar:
        st.markdown("## 🎗️ MSK Oncología")
        st.write(f"**Director:** {name}")
        st.divider()
        modulo = st.radio(
            "Módulo activo",
            ["A · Protocolos Clínicos", "B · The Bridge", "C · Dashboard"],
            index=0,
        )
        st.divider()
        authenticator.logout(button_name="Cerrar sesión", location="sidebar")

    # 3. Carga de Datos (Lazy loading)
    try:
        journey_df    = load_journey()
        paquetes_df   = load_paquetes()
        catalogo_df   = load_catalogo()
        financiero_df = load_financiero()
        kpis_df       = load_kpis()
    except Exception as e:
        st.error(f"❌ Error crítico cargando datos: {e}")
        st.stop()

    # 4. Enrutamiento de Vistas
    if modulo == "A · Protocolos Clínicos":
        render_module_a(journey_df, paquetes_df, catalogo_df)
    elif modulo == "B · The Bridge":
        render_module_b(paquetes_df, financiero_df, kpis_df)
    elif modulo == "C · Dashboard":
        render_module_c(financiero_df, paquetes_df)

if __name__ == "__main__":
    main()
