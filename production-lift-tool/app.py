import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf

# ---------------------------
# PAGE SETUP
# ---------------------------
st.set_page_config(page_title="Production & Lift Tool", layout="wide")

st.title("Production Engineering Tool")
st.write("Decline Curve Analysis + Lift Method Selection")


# ---------------------------
# LIVE OIL PRICE
# ---------------------------
def get_live_oil_price():
    try:
        ticker = yf.Ticker("CL=F")  # WTI crude futures
        data = ticker.history(period="1d")
        price = float(data["Close"].iloc[-1])
        return round(price, 2)
    except Exception:
        return 70.0


# ---------------------------
# DECLINE CURVE FUNCTIONS
# ---------------------------
def arps_decline(qi, di, t, model, b=0.5):
    if model == "Exponential":
        return qi * np.exp(-di * t)
    elif model == "Harmonic":
        return qi / (1 + di * t)
    elif model == "Hyperbolic":
        return qi / ((1 + b * di * t) ** (1 / b))
    else:
        return qi * np.exp(-di * t)


def cumulative(q, dt=1.0):
    return np.cumsum(q * dt)


def eur(q, abandonment_rate, dt=1.0):
    return np.sum(q[q > abandonment_rate] * dt)


def safe_glr(gas_mcf, oil_bbl):
    if pd.notna(gas_mcf) and pd.notna(oil_bbl) and oil_bbl > 0:
        return (gas_mcf * 1000) / oil_bbl
    return 0


def glr_profile(glr_initial, glr_final, t):
    return np.linspace(glr_initial, glr_final, len(t))


# ---------------------------
# LIFT ENGINE FUNCTIONS
# ---------------------------
def lift_decision(rate, glr, oil_price, cost_per_bbl, required_margin,
                  plunger_rate, gl_rate, hpgl_rate, esp_rate):
    margin = oil_price - cost_per_bbl

    if rate <= plunger_rate:
        return "Plunger Lift"

    elif rate >= esp_rate and glr <= 2000:
        return "ESP"

    elif rate >= esp_rate and glr > 2000:
        return "ESP or HPGL"

    elif rate >= hpgl_rate and glr >= gl_rate and margin >= required_margin:
        return "HPGL"

    elif rate >= hpgl_rate and margin < required_margin:
        return "HPGL or Gas Lift"

    elif rate >= gl_rate and glr >= gl_rate:
        return "Conventional Gas Lift"

    elif rate >= gl_rate and rate < hpgl_rate:
        return "Gas Lift or HPGL"

    elif rate > plunger_rate and rate < gl_rate:
        return "Plunger or Gas Lift"

    else:
        return "Engineering Review"


def lifecycle_stage(rate, glr, oil_price, cost_per_bbl, required_margin,
                    plunger_rate, gl_rate, hpgl_rate, esp_rate):
    margin = oil_price - cost_per_bbl

    if rate > esp_rate and glr <= 2000:
        return "High-rate stage: ESP candidate"
    elif glr > 500 and rate > hpgl_rate and margin >= required_margin:
        return "Gas lift stage: HPGL likely"
    elif glr > 500:
        return "Gas lift stage: Conventional Gas Lift"
    elif rate <= plunger_rate:
        return "Late life: Plunger Lift"
    else:
        return "Intermediate stage"


def lift_timeline(q, glr_series, oil_price, cost_per_bbl, required_margin,
                  plunger_rate, gl_rate, hpgl_rate, esp_rate):
    timeline = []

    for rate, glr in zip(q, glr_series):
        method = lift_decision(
            rate, glr, oil_price, cost_per_bbl, required_margin,
            plunger_rate, gl_rate, hpgl_rate, esp_rate
        )
        timeline.append(method)

    return timeline


def transition_text(row):
    if row["Lift_3M"] == row["Lift_12M"] == row["Lift_36M"]:
        return f"Remain on {row['Lift_36M']}"
    return f"{row['Lift_3M']} → {row['Lift_12M']} → {row['Lift_36M']}"


# ---------------------------
# TABS
# ---------------------------
tab1, tab2, tab3 = st.tabs(["Decline Curve", "Lift Selection", "Upload Data"])


# ---------------------------
# TAB 1: DECLINE CURVE
# ---------------------------
with tab1:
    st.header("Decline Curve Analysis")

    model = st.selectbox("Decline Model", ["Exponential", "Harmonic", "Hyperbolic"])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        qi = st.number_input("Initial Rate (qi)", value=1000.0, key="tab1_qi")

    with col2:
        di = st.number_input("Initial Decline Rate (di, fraction)", value=0.10, key="tab1_di")

    with col3:
        abandon = st.number_input("Abandonment Rate (BOPD)", value=50.0, key="tab1_abandon")

    with col4:
        t_max = st.number_input("Time (months)", value=60, key="tab1_tmax")

    b = 0.5
    if model == "Hyperbolic":
        b = st.number_input("b-factor", value=0.5, min_value=0.01, max_value=2.0, key="tab1_b")

    st.subheader("Lift Inputs for Lifecycle Forecast")

    col1, col2, col3 = st.columns(3)

    with col1:
        glr_initial = st.number_input("Initial GLR (scf/bbl)", value=1200.0, key="tab1_glr_initial")

    with col2:
        oil_price = st.number_input("Oil Price ($/bbl)", value=get_live_oil_price(), key="tab1_oil_price")

    with col3:
        cost_per_bbl = st.number_input("Operating Cost ($/bbl)", value=6.0, key="tab1_cost")

    glr_final = st.number_input("Final GLR (scf/bbl)", value=300.0, key="tab1_glr_final")

    required_margin = st.number_input(
        "Required Margin for HPGL ($/bbl)",
        value=20.0,
        key="tab1_required_margin"
    )

    st.subheader("Rate Thresholds (BOPD)")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        plunger_rate = st.number_input("Plunger Threshold", value=300.0, key="tab1_plunger")

    with col2:
        gl_rate = st.number_input("Gas Lift Threshold", value=500.0, key="tab1_gl")

    with col3:
        hpgl_rate = st.number_input("HPGL Threshold", value=800.0, key="tab1_hpgl")

    with col4:
        esp_rate = st.number_input("ESP Threshold", value=2000.0, key="tab1_esp")

    # Calculations
    t = np.arange(0, int(t_max) + 1)
    q = arps_decline(qi, di, t, model, b)
    cum = cumulative(q)
    eur_value = eur(q, abandon)
    glr_series = glr_profile(glr_initial, glr_final, t)

    lift_methods = lift_timeline(
        q, glr_series, oil_price, cost_per_bbl, required_margin,
        plunger_rate, gl_rate, hpgl_rate, esp_rate
    )

    # Outputs
    st.subheader("Production Rate")
    left, center, right = st.columns([1, 3, 1])
    with center:
        st.line_chart({"Rate": q})

    st.subheader("Cumulative Production")
    left, center, right = st.columns([1, 3, 1])
    with center:
        st.line_chart({"Cumulative": cum})

    st.subheader("GLR Profile")
    left, center, right = st.columns([1, 3, 1])
    with center:
        st.line_chart({"GLR": glr_series})

    st.metric("Estimated EUR", f"{eur_value:.0f} bbl")

    st.dataframe({
        "Time (months)": t,
        "Rate": q,
        "GLR": glr_series,
        "Cumulative": cum,
        "Lift Method": lift_methods
    })

    st.subheader("Lift Transition Points")

    transitions = []
    for i in range(1, len(lift_methods)):
        if lift_methods[i] != lift_methods[i - 1]:
            transitions.append((t[i], lift_methods[i]))

    if transitions:
        for time, method in transitions:
            st.write(f"Month {time}: Switch to {method}")
    else:
        st.write("No lift transitions within selected timeframe")


# ---------------------------
# TAB 2: LIFT SELECTION
# ---------------------------
with tab2:
    st.header("Lift Method Decision Engine")

    st.subheader("Well Inputs")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        rate = st.number_input("Production Rate (BOPD)", value=800.0, key="tab2_rate")

    with col2:
        glr = st.number_input("GLR (scf/bbl)", value=600.0, key="tab2_glr")

    with col3:
        oil_price = st.number_input("Oil Price ($/bbl)", value=get_live_oil_price(), key="tab2_oil_price")

    with col4:
        cost_per_bbl = st.number_input("Operating Cost ($/bbl)", value=6.0, key="tab2_cost")

    required_margin = st.number_input(
        "Required Margin for HPGL ($/bbl)",
        value=20.0,
        key="tab2_required_margin"
    )

    st.subheader("Rate Thresholds (BOPD)")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        plunger_rate = st.number_input("Plunger Threshold", value=300.0, key="tab2_plunger")

    with col2:
        gl_rate = st.number_input("Gas Lift Threshold", value=500.0, key="tab2_gl")

    with col3:
        hpgl_rate = st.number_input("HPGL Threshold", value=800.0, key="tab2_hpgl")

    with col4:
        esp_rate = st.number_input("ESP Threshold", value=2000.0, key="tab2_esp")

    result = lift_decision(
        rate, glr, oil_price, cost_per_bbl, required_margin,
        plunger_rate, gl_rate, hpgl_rate, esp_rate
    )

    stage = lifecycle_stage(
        rate, glr, oil_price, cost_per_bbl, required_margin,
        plunger_rate, gl_rate, hpgl_rate, esp_rate
    )

    st.subheader("Recommended Lift Method")
    st.success(result)

    st.subheader("Production Lifecycle Stage")
    st.info(stage)

    st.subheader("Economics")
    st.write(f"Net margin = ${oil_price - cost_per_bbl:.2f}/bbl")
    st.write(f"Required HPGL margin = ${required_margin:.2f}/bbl")


# ---------------------------
# TAB 3: UPLOAD DATA
# ---------------------------
with tab3:
    st.header("Upload Enverus Production Data")

    uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

    if uploaded_file is None:
        st.info("Upload your Enverus CSV file to calculate lifecycle lift recommendations.")
    else:
        df = pd.read_csv(uploaded_file)

        st.subheader("Raw Uploaded Data")
        st.dataframe(df.head())

        st.subheader("Available Columns")
        st.write(list(df.columns))

        required_columns = [
            "First3MonthOil_BBL",
            "First3MonthGas_MCF",
            "First12MonthOil_BBL",
            "First12MonthGas_MCF",
            "First36MonthOil_BBL",
            "First36MonthGas_MCF",
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            st.error("The uploaded file is missing these required columns:")
            st.write(missing_columns)
        else:
            # Calculations
            df["BOPD_3M"] = df["First3MonthOil_BBL"] / 91
            df["BOPD_12M"] = df["First12MonthOil_BBL"] / 365
            df["BOPD_36M"] = df["First36MonthOil_BBL"] / 1095

            df["GLR_3M"] = df.apply(
                lambda row: safe_glr(row["First3MonthGas_MCF"], row["First3MonthOil_BBL"]),
                axis=1
            )
            df["GLR_12M"] = df.apply(
                lambda row: safe_glr(row["First12MonthGas_MCF"], row["First12MonthOil_BBL"]),
                axis=1
            )
            df["GLR_36M"] = df.apply(
                lambda row: safe_glr(row["First36MonthGas_MCF"], row["First36MonthOil_BBL"]),
                axis=1
            )

            st.subheader("Screening Inputs")

            col1, col2, col3 = st.columns(3)

            with col1:
                oil_price = st.number_input(
                    "Oil Price ($/bbl)",
                    value=get_live_oil_price(),
                    key="upload_oil_price"
                )

            with col2:
                cost_per_bbl = st.number_input(
                    "Operating Cost ($/bbl)",
                    value=6.0,
                    key="upload_cost"
                )

            with col3:
                required_margin = st.number_input(
                    "Required Margin for HPGL ($/bbl)",
                    value=20.0,
                    key="upload_margin"
                )

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                plunger_rate = st.number_input("Plunger Threshold", value=300.0, key="upload_plunger")

            with col2:
                gl_rate = st.number_input("Gas Lift Threshold", value=500.0, key="upload_gl")

            with col3:
                hpgl_rate = st.number_input("HPGL Threshold", value=800.0, key="upload_hpgl")

            with col4:
                esp_rate = st.number_input("ESP Threshold", value=2000.0, key="upload_esp")

            df["Lift_3M"] = df.apply(
                lambda row: lift_decision(
                    row["BOPD_3M"],
                    row["GLR_3M"],
                    oil_price,
                    cost_per_bbl,
                    required_margin,
                    plunger_rate,
                    gl_rate,
                    hpgl_rate,
                    esp_rate
                ),
                axis=1
            )

            df["Lift_12M"] = df.apply(
                lambda row: lift_decision(
                    row["BOPD_12M"],
                    row["GLR_12M"],
                    oil_price,
                    cost_per_bbl,
                    required_margin,
                    plunger_rate,
                    gl_rate,
                    hpgl_rate,
                    esp_rate
                ),
                axis=1
            )

            df["Lift_36M"] = df.apply(
                lambda row: lift_decision(
                    row["BOPD_36M"],
                    row["GLR_36M"],
                    oil_price,
                    cost_per_bbl,
                    required_margin,
                    plunger_rate,
                    gl_rate,
                    hpgl_rate,
                    esp_rate
                ),
                axis=1
            )

            df["Lift Transition Path"] = df.apply(transition_text, axis=1)

            identity_columns = []
            for col in ["WellName", "Well Name", "API_UWI", "ENVBasin", "ENVOperator", "County"]:
                if col in df.columns:
                    identity_columns.append(col)

            output_columns = identity_columns + [
                "BOPD_3M",
                "GLR_3M",
                "Lift_3M",
                "BOPD_12M",
                "GLR_12M",
                "Lift_12M",
                "BOPD_36M",
                "GLR_36M",
                "Lift_36M",
                "Lift Transition Path"
            ]

            st.subheader("Lifecycle Lift Recommendations")
            st.dataframe(df[output_columns])

            st.subheader("Summary Counts")
            st.write(df["Lift_36M"].value_counts())

            st.subheader("Economics")
            st.write(f"Net margin = ${oil_price - cost_per_bbl:.2f}/bbl")
            st.write(f"Required HPGL margin = ${required_margin:.2f}/bbl")
