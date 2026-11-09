import streamlit as st
import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "greenfund.db"
EVIDENCE_DIR = APP_DIR / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="GreenFund IITG", page_icon="🌱", layout="wide")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            update_text TEXT NOT NULL,
            progress REAL NOT NULL,
            funds_received REAL NOT NULL,
            funds_spent REAL NOT NULL,
            evidence TEXT NOT NULL,
            created_at TEXT NOT NULL,
            investor_status TEXT NOT NULL DEFAULT 'Pending review',
            investor_comment TEXT DEFAULT ''
        )
    """)
    conn.commit()
    return conn

def save_update(project_name, update_text, progress, funds_received, funds_spent, evidence_files):
    saved_files = []
    for uploaded in evidence_files:
        suffix = Path(uploaded.name).suffix.lower()
        safe_name = f"{uuid.uuid4().hex}{suffix}"
        destination = EVIDENCE_DIR / safe_name
        destination.write_bytes(uploaded.getbuffer())
        saved_files.append({"name": uploaded.name, "path": str(destination.relative_to(APP_DIR))})

    conn = get_connection()
    conn.execute(
        """INSERT INTO updates
        (project_name, update_text, progress, funds_received, funds_spent, evidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (project_name, update_text, progress, funds_received, funds_spent,
         json.dumps(saved_files), datetime.now().strftime("%d %b %Y, %I:%M %p"))
    )
    conn.commit()
    conn.close()

def load_updates():
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, project_name, update_text, progress, funds_received,
        funds_spent, evidence, created_at, investor_status, investor_comment
        FROM updates ORDER BY id DESC"""
    ).fetchall()
    conn.close()
    return rows

def update_review(update_id, status, comment):
    conn = get_connection()
    conn.execute(
        "UPDATE updates SET investor_status=?, investor_comment=? WHERE id=?",
        (status, comment, update_id)
    )
    conn.commit()
    conn.close()

st.title("🌱 GreenFund IITG")
st.caption("A student prototype for solar project evaluation, transparent progress reporting and investor review.")

tab1, tab2, tab3 = st.tabs([
    "☀️ Solar calculator",
    "📸 Project updates",
    "🤝 Investor review"
])

with tab1:
    st.header("Solar project calculator")
    st.write("Enter the building's electricity details and the proposed solar system details. Results are estimates, not a formal engineering or investment audit.")

    left, right = st.columns(2)
    with left:
        st.subheader("Building electricity details")
        monthly_units = st.number_input("Monthly grid electricity use (kWh)", min_value=0.0, value=5000.0, step=100.0)
        tariff = st.number_input("Electricity tariff (₹ per kWh)", min_value=0.0, value=8.0, step=0.5)
        grid_factor = st.number_input(
            "Grid emission factor (kg CO₂ per kWh)",
            min_value=0.0, value=0.716, step=0.001, format="%.3f",
            help="Demo value only. Replace with the latest applicable official CEA value and cite its source/year."
        )
    with right:
        st.subheader("Proposed solar system")
        capacity = st.number_input("Solar capacity (kW)", min_value=0.1, value=10.0, step=0.5)
        sun_hours = st.number_input("Equivalent full-sun generation hours per day", min_value=0.0, value=4.0, step=0.1)
        performance = st.slider("System performance factor (%)", min_value=50, max_value=95, value=80)
        self_use = st.slider("Share of solar electricity used in the building (%)", min_value=0, max_value=100, value=90)
        cost_per_kw = st.number_input("Installed cost per kW (₹)", min_value=0.0, value=45000.0, step=1000.0)
        annual_om = st.number_input("Annual maintenance cost (₹)", min_value=0.0, value=10000.0, step=1000.0)

    if st.button("Calculate solar and finance results", type="primary"):
        annual_grid_use = monthly_units * 12
        annual_solar_generation = capacity * sun_hours * 365 * (performance / 100)
        solar_used_in_building = annual_solar_generation * (self_use / 100)
        grid_electricity_displaced = min(annual_grid_use, solar_used_in_building)

        emissions_before = annual_grid_use * grid_factor
        emissions_after = max(0, annual_grid_use - grid_electricity_displaced) * grid_factor
        co2_avoided = emissions_before - emissions_after

        annual_bill_savings = grid_electricity_displaced * tariff
        net_annual_savings = annual_bill_savings - annual_om
        investment = capacity * cost_per_kw
        payback = investment / net_annual_savings if net_annual_savings > 0 else None

        st.subheader("Estimated results")
        a, b, c = st.columns(3)
        a.metric("Annual solar generation", f"{annual_solar_generation:,.0f} kWh")
        b.metric("Annual CO₂ avoided", f"{co2_avoided/1000:,.2f} tonnes")
        c.metric("Initial investment", f"₹{investment:,.0f}")

        d, e, f = st.columns(3)
        d.metric("Annual electricity bill savings", f"₹{annual_bill_savings:,.0f}")
        e.metric("Net annual savings", f"₹{net_annual_savings:,.0f}")
        f.metric("Simple payback period", f"{payback:.1f} years" if payback is not None else "Not reached")

        st.write(f"**Estimated annual grid emissions before solar:** {emissions_before/1000:,.2f} tonnes CO₂")
        st.write(f"**Estimated annual grid emissions after solar:** {emissions_after/1000:,.2f} tonnes CO₂")
        st.info(
            "Calculation assumptions: solar generation = capacity × equivalent full-sun hours × 365 × performance factor. "
            "Only solar electricity that replaces the building's grid electricity is counted for bill savings and avoided emissions. "
            "Export payments, taxes, financing interest, panel degradation and equipment replacement are not included."
        )
        st.warning(
            "The default emission factor and example inputs are placeholders for demonstrating the app. "
            "Before presenting results as IIT Guwahati estimates, replace them with sourced campus data and the latest applicable official emission factor."
        )

with tab2:
    st.header("Project progress and evidence")
    st.write("Project teams can post regular updates and upload photos, videos, invoices or progress documents.")
    with st.form("project_update_form", clear_on_submit=True):
        project_name = st.text_input("Project name", placeholder="Example: Rooftop solar pilot – Hostel X")
        update_text = st.text_area("What progress has been made?", placeholder="Describe work completed, delays, next steps and any issues.")
        progress = st.slider("Overall project progress (%)", 0, 100, 10)
        col1, col2 = st.columns(2)
        with col1:
            funds_received = st.number_input("Total funding received so far (₹)", min_value=0.0, value=0.0, step=1000.0)
        with col2:
            funds_spent = st.number_input("Total amount spent so far (₹)", min_value=0.0, value=0.0, step=1000.0)
        evidence_files = st.file_uploader(
            "Upload evidence (photos, videos, invoices or reports)",
            type=["png", "jpg", "jpeg", "mp4", "mov", "pdf"],
            accept_multiple_files=True
        )
        submitted = st.form_submit_button("Submit project update", type="primary")
        if submitted:
            if not project_name.strip() or not update_text.strip():
                st.error("Please enter a project name and a progress update.")
            elif funds_spent > funds_received:
                st.error("Amount spent cannot be greater than total funding received. Check the figures.")
            else:
                save_update(project_name.strip(), update_text.strip(), progress, funds_received, funds_spent, evidence_files or [])
                st.success("Update saved. It is now available for investor review.")

    st.divider()
    st.subheader("Previously submitted updates")
    updates = load_updates()
    if not updates:
        st.info("No project updates have been submitted yet.")
    for row in updates:
        uid, name, description, pct, received, spent, evidence_json, created, status, comment = row
        with st.expander(f"{name} — {created} — {status}"):
            st.write(description)
            st.progress(int(pct))
            st.write(f"**Progress:** {pct:.0f}%")
            st.write(f"**Funding received:** ₹{received:,.0f}  |  **Spent:** ₹{spent:,.0f}  |  **Unspent:** ₹{received-spent:,.0f}")
            evidence = json.loads(evidence_json)
            if evidence:
                st.write("**Uploaded evidence:**")
                for item in evidence:
                    file_path = APP_DIR / item["path"]
                    if file_path.exists():
                        st.write(f"- {item['name']}")
                        if file_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                            st.image(str(file_path), width=300)
                        else:
                            st.download_button(
                                f"Open/download {item['name']}",
                                data=file_path.read_bytes(),
                                file_name=item["name"],
                                key=f"download_{uid}_{item['name']}"
                            )
            else:
                st.caption("No supporting files uploaded.")
            st.write(f"**Investor review:** {status}")
            if comment:
                st.write(f"**Investor comment:** {comment}")

with tab3:
    st.header("Investor review panel")
    st.write("An investor or reviewer can inspect submitted updates and record a decision. In this classroom prototype, this is a demonstration workflow, not a legally binding approval.")
    updates = load_updates()
    if not updates:
        st.info("There are no submitted updates to review yet. Submit an update in the Project updates tab first.")
    else:
        labels = {
            f"Update #{r[0]} — {r[1]} — {r[7]}": r
            for r in updates
        }
        selected_label = st.selectbox("Choose a project update to review", list(labels.keys()))
        row = labels[selected_label]
        uid, name, description, pct, received, spent, evidence_json, created, status, comment = row
        st.subheader(name)
        st.write(description)
        st.write(f"**Progress:** {pct:.0f}%")
        st.write(f"**Funding received:** ₹{received:,.0f}")
        st.write(f"**Funding spent:** ₹{spent:,.0f}")
        st.write(f"**Current status:** {status}")
        evidence = json.loads(evidence_json)
        st.write(f"**Evidence files uploaded:** {len(evidence)}")
        for item in evidence:
            st.write(f"- {item['name']}")
            file_path = APP_DIR / item["path"]
            if file_path.exists() and file_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                st.image(str(file_path), width=250)
            elif file_path.exists():
                st.download_button(
                    f"Download {item['name']}",
                    data=file_path.read_bytes(),
                    file_name=item["name"],
                    key=f"review_download_{uid}_{item['name']}"
                )
        st.caption("Reviewers should check evidence and figures before recording a decision. Uploading a file alone does not verify that a claim is true.")
        decision = st.radio("Review decision", ["Pending review", "Approved by reviewer", "Changes requested"], index=["Pending review", "Approved by reviewer", "Changes requested"].index(status) if status in ["Pending review", "Approved by reviewer", "Changes requested"] else 0)
        reviewer_comment = st.text_area("Reviewer comment", value=comment or "", key=f"comment_{uid}")
        if st.button("Save review decision", type="primary"):
            update_review(uid, decision, reviewer_comment)
            st.success("Review decision saved.")

st.divider()
st.caption("GreenFund IITG student prototype • Data is stored locally on the computer running this app. Do not upload confidential financial or personal information.")
